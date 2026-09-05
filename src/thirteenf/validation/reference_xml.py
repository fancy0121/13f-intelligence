"""Independent SEC XML reference parser using only the Python stdlib."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime


_UNSAFE = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_INTEGER = re.compile(r"^(?:0|[1-9][0-9]*)$")


class ReferenceXmlError(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceHolding:
    row_ordinal: int
    issuer: str
    title_of_class: str
    cusip: str
    value: int
    shares: int
    put_call: str
    shares_type: str


@dataclass(frozen=True)
class ReferenceCover:
    submission_type: str
    report_period: str
    is_amendment: bool
    amendment_number: int | None
    amendment_type: str | None


def reference_rows(xml_bytes: bytes) -> tuple[ReferenceHolding, ...]:
    root = _root(xml_bytes)
    nodes = [node for node in root.iter() if _local(node.tag) == "infoTable"]
    rows = []
    for ordinal, node in enumerate(nodes, start=1):
        put_call = _text(node, "putCall").upper()
        shares_type = _text(node, "sshPrnamtType").upper()
        if put_call not in {"", "CALL", "PUT"}:
            raise ReferenceXmlError(f"row {ordinal}: invalid putCall")
        if shares_type not in {"SH", "PRN"}:
            raise ReferenceXmlError(f"row {ordinal}: invalid sshPrnamtType")
        rows.append(
            ReferenceHolding(
                row_ordinal=ordinal,
                issuer=_text(node, "nameOfIssuer"),
                title_of_class=_text(node, "titleOfClass"),
                cusip=_text(node, "cusip").upper(),
                value=_number(_text(node, "value"), ordinal, "value"),
                shares=_number(_text(node, "sshPrnamt"), ordinal, "shares"),
                put_call=put_call,
                shares_type=shares_type,
            )
        )
    return tuple(rows)


def reference_cover(xml_bytes: bytes) -> ReferenceCover:
    root = _root(xml_bytes)
    submission_type = _text(root, "submissionType").upper()
    if submission_type not in {"13F-HR", "13F-HR/A"}:
        raise ReferenceXmlError(f"unsupported submissionType {submission_type!r}")
    report_raw = _text(root, "reportCalendarOrQuarter")
    report_period = _date(report_raw)
    amended_raw = _text(root, "isAmendment").lower()
    if amended_raw not in {"true", "false"}:
        raise ReferenceXmlError("missing or invalid isAmendment")
    is_amendment = amended_raw == "true"
    if is_amendment != submission_type.endswith("/A"):
        raise ReferenceXmlError("contradictory amendment status")
    amendment_nodes = [
        node for node in root.iter() if _local(node.tag) == "amendmentType"
    ]
    number_raw = _text(root, "amendmentNo")
    if not is_amendment:
        if number_raw or amendment_nodes:
            raise ReferenceXmlError("base filing contains amendment metadata")
        return ReferenceCover(submission_type, report_period, False, None, None)
    if len(amendment_nodes) != 1 or not _INTEGER.fullmatch(number_raw):
        raise ReferenceXmlError("incomplete amendment metadata")
    number = int(number_raw)
    if number < 1:
        raise ReferenceXmlError("invalid amendment number")
    value = (amendment_nodes[0].text or "").strip().upper()
    if value == "NEW HOLDINGS":
        amendment_type = "ADD_NEW_HOLDINGS"
    elif value == "RESTATEMENT":
        amendment_type = value
    else:
        raise ReferenceXmlError(f"unsupported amendment type {value!r}")
    return ReferenceCover(
        submission_type,
        report_period,
        True,
        number,
        amendment_type,
    )


def _root(xml_bytes: bytes):
    if _UNSAFE.search(xml_bytes):
        raise ReferenceXmlError("DTD and entity declarations are forbidden")
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ReferenceXmlError(f"malformed XML: {exc}") from exc


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(node, name: str) -> str:
    for child in node.iter():
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _number(value: str, ordinal: int, field: str) -> int:
    if not _INTEGER.fullmatch(value):
        raise ReferenceXmlError(f"row {ordinal}: invalid {field} {value!r}")
    return int(value)


def _date(value: str) -> str:
    for pattern in ("%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ReferenceXmlError(f"invalid report period {value!r}")
