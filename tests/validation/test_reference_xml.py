from __future__ import annotations

import pytest

from thirteenf.validation.reference_xml import ReferenceXmlError, reference_rows


def test_reference_parser_matches_real_sec_fixture(repo_root):
    rows = reference_rows(
        (repo_root / "tests" / "fixtures" / "trian_Q22025_info_table.xml").read_bytes()
    )
    assert len(rows) == 11
    assert rows[0].cusip == "G3421J106"
    assert rows[0].shares == 1086357
    assert rows[0].value == 236554237


def test_reference_parser_rejects_entities():
    with pytest.raises(ReferenceXmlError, match="DTD|entity"):
        reference_rows(
            b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
            b"<informationTable>&e;</informationTable>"
        )
