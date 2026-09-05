"""Content-addressed storage for immutable SEC source documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path


ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


@dataclass(frozen=True)
class RawObject:
    checksum: str
    relative_path: str
    byte_size: int


class RawStore:
    """Store source bytes by SHA-256 and retain accession manifest versions."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, relative: Path) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"raw path escapes root: {relative}")
        return candidate

    @staticmethod
    def _canonical_json(payload: dict) -> bytes:
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _write_atomic(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass

    def put(self, content: bytes) -> RawObject:
        checksum = hashlib.sha256(content).hexdigest()
        relative = Path("objects") / "sha256" / checksum[:2] / checksum
        path = self._path(relative)
        if path.exists():
            existing = path.read_bytes()
            if hashlib.sha256(existing).hexdigest() != checksum:
                raise RuntimeError(f"content-address collision at {relative.as_posix()}")
        else:
            self._write_atomic(path, content)
        return RawObject(
            checksum=checksum,
            relative_path=relative.as_posix(),
            byte_size=len(content),
        )

    def read_object(self, relative_path: str, checksum: str) -> bytes:
        path = self._path(Path(relative_path))
        content = path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        if actual != checksum:
            raise RuntimeError(
                f"raw object checksum mismatch: expected {checksum}, got {actual}"
            )
        return content

    @staticmethod
    def _identity(cik: int, accession: str) -> tuple[str, str]:
        if int(cik) <= 0 or not ACCESSION_RE.fullmatch(accession):
            raise ValueError("invalid CIK or accession identity")
        return f"{int(cik):010d}", accession.replace("-", "")

    def manifest_path(self, cik: int, accession: str) -> Path:
        cik_text, accession_text = self._identity(cik, accession)
        return self._path(
            Path("manifests") / cik_text / f"{accession_text}.json"
        )

    def legacy_manifest_path(self, cik: int, accession: str) -> Path:
        _, accession_text = self._identity(cik, accession)
        return self._path(Path(str(int(cik))) / accession_text / "manifest.json")

    def load_manifest(self, cik: int, accession: str) -> dict | None:
        for path in (
            self.manifest_path(cik, accession),
            self.legacy_manifest_path(cik, accession),
        ):
            if not path.exists():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"invalid raw manifest {path}") from exc
            if not isinstance(value, dict):
                raise RuntimeError(f"invalid raw manifest object {path}")
            return value
        return None

    def write_manifest(self, cik: int, accession: str, payload: dict) -> Path:
        cik_text, accession_text = self._identity(cik, accession)
        content = self._canonical_json(payload)
        manifest_checksum = hashlib.sha256(content).hexdigest()
        version_path = self._path(
            Path("manifest_versions")
            / cik_text
            / accession_text
            / f"{manifest_checksum}.json"
        )
        if not version_path.exists():
            self._write_atomic(version_path, content)

        current = self.manifest_path(cik, accession)
        self._write_atomic(current, content)
        # Transitional mirror keeps the existing offline normalizer working.
        self._write_atomic(self.legacy_manifest_path(cik, accession), content)
        return current

    def materialize_legacy(
        self,
        cik: int,
        accession: str,
        logical_name: str,
        content: bytes,
    ) -> Path:
        if Path(logical_name).name != logical_name:
            raise ValueError("logical_name must be a file name")
        _, accession_text = self._identity(cik, accession)
        path = self._path(Path(str(int(cik))) / accession_text / logical_name)
        self._write_atomic(path, content)
        return path
