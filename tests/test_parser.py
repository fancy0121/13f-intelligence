from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from thirteenf.parser import XmlParseError, parse_info_table


SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>APPLE INC</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>037833100</cusip>
    <value>1000000</value>
    <shrsOrPrnAmt>
      <sshPrnamt>5000</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
    <otherManager>0</otherManager>
    <votingAuthority>
      <Sole>5000</Sole>
      <Shared>0</Shared>
      <None>0</None>
    </votingAuthority>
  </infoTable>
  <infoTable>
    <nameOfIssuer>SOME CO</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>123456789</cusip>
    <value>500</value>
    <shrsOrPrnAmt>
      <sshPrnamt>100</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <putCall>PUT</putCall>
    <investmentDiscretion>SOLE</investmentDiscretion>
    <otherManager>0</otherManager>
  </infoTable>
</informationTable>
"""


def test_parse_basic_rows():
    rows = parse_info_table(SAMPLE)
    assert len(rows) == 2
    assert rows[0].cusip == "037833100"
    assert rows[0].name_of_issuer == "APPLE INC"
    assert rows[0].shares == 5000
    assert rows[0].value == 1000000
    assert rows[0].put_call == ""
    assert rows[1].put_call == "PUT"
    assert rows[1].row_ordinal == 2


def test_parse_namespaced_prefix():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<n1:informationTable xmlns:n1="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <n1:infoTable>
    <n1:nameOfIssuer>APPLE INC</n1:nameOfIssuer>
    <n1:titleOfClass>COM</n1:titleOfClass>
    <n1:cusip>037833100</n1:cusip>
    <n1:value>1000000</n1:value>
    <n1:shrsOrPrnAmt>
      <n1:sshPrnamt>5000</n1:sshPrnamt>
      <n1:sshPrnamtType>SH</n1:sshPrnamtType>
    </n1:shrsOrPrnAmt>
    <n1:investmentDiscretion>SOLE</n1:investmentDiscretion>
    <n1:otherManager>0</n1:otherManager>
  </n1:infoTable>
</n1:informationTable>
"""
    rows = parse_info_table(xml)
    assert len(rows) == 1
    assert rows[0].cusip == "037833100"
    assert rows[0].shares == 5000
    assert rows[0].value == 1000000


def test_missing_fields_tolerated():
    xml = b"""<?xml version="1.0"?>
<informationTable>
  <infoTable>
    <nameOfIssuer>PARTIAL</nameOfIssuer>
    <cusip></cusip>
    <value>abc</value>
  </infoTable>
</informationTable>
"""
    rows = parse_info_table(xml)
    assert len(rows) == 1
    assert rows[0].cusip == ""
    assert rows[0].value is None
    assert rows[0].shares is None
    assert rows[0].put_call == ""


def test_malformed_xml_raises():
    with pytest.raises(XmlParseError):
        parse_info_table(b"<informationTable><infoTable></informationTable>")
