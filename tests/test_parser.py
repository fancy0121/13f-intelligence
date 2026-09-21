from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from thirteenf.parser import (
    HoldingValidationError,
    XmlParseError,
    parse_cover_page,
    parse_info_table,
)
from thirteenf.validation.reference_xml import reference_cover, ReferenceXmlError


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


@pytest.mark.parametrize('parser', [parse_cover_page, reference_cover])
def test_real_sec_base_cover_can_omit_optional_amendment_flag(parser):
    # SEC 13F v1.9 eis_13F_Filer.xsd: isAmendment minOccurs="0".
    # Untouched raw source: 1061768/000106176826000010/primary_doc.xml.
    import hashlib
    data = (ROOT / 'tests/fixtures/baupost_2026q2_primary_doc.xml').read_bytes()
    assert hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest() == (
        '607717660ee58e7bb121991e4fa26c7969f13741ad0d051a81d0dc88a0ac7326')
    assert b'<isAmendment>' not in data
    cover = parser(data)
    assert cover.submission_type == '13F-HR'
    assert cover.report_period == '2026-06-30'
    assert cover.amendment_number is None
    assert cover.amendment_type is None


@pytest.mark.parametrize('parser,error', [(parse_cover_page, XmlParseError), (reference_cover, ReferenceXmlError)])
@pytest.mark.parametrize('flag', ['', '<isAmendment/>', '<isAmendment>maybe</isAmendment>'])
def test_amendment_cannot_infer_an_invalid_or_missing_flag(parser, error, flag):
    data = f'''<edgarSubmission><headerData><submissionType>13F-HR/A</submissionType></headerData>
    <formData><coverPage><reportCalendarOrQuarter>06-30-2026</reportCalendarOrQuarter>
    {flag}<amendmentNo>1</amendmentNo><amendmentInfo><amendmentType>RESTATEMENT</amendmentType>
    </amendmentInfo></coverPage></formData></edgarSubmission>'''.encode()
    with pytest.raises(error):
        parser(data)


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


def test_optional_fields_may_be_missing():
    xml = b"""<?xml version="1.0"?>
<informationTable>
  <infoTable>
    <nameOfIssuer>PARTIAL</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>123456789</cusip>
    <value>10</value>
    <shrsOrPrnAmt>
      <sshPrnamt>2</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
  </infoTable>
</informationTable>
"""
    rows = parse_info_table(xml)
    assert len(rows) == 1
    assert rows[0].cusip == "123456789"
    assert rows[0].value == 10
    assert rows[0].shares == 2
    assert rows[0].put_call == ""
    assert rows[0].investment_discretion == ""
    assert rows[0].other_manager == ""


def test_malformed_xml_raises():
    with pytest.raises(XmlParseError):
        parse_info_table(b"<informationTable><infoTable></informationTable>")


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE x><informationTable/>',
        (
            b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
            b"<informationTable>&e;</informationTable>"
        ),
    ],
)
def test_dtd_or_external_entity_is_rejected(payload):
    with pytest.raises(XmlParseError, match="DTD|entity"):
        parse_info_table(payload)


@pytest.mark.parametrize(
    ("field_xml", "field_name"),
    [
        ("<value></value>", "value"),
        ("<value>1.5</value>", "value"),
        ("<value>-1</value>", "value"),
        ("<value>1</value>", "shares"),
    ],
)
def test_missing_or_invalid_critical_numeric_fields_raise(field_xml, field_name):
    shares = """
    <shrsOrPrnAmt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    """ if field_name == "shares" else """
    <shrsOrPrnAmt>
      <sshPrnamt>2</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    """
    xml = f"""<?xml version="1.0"?>
    <informationTable><infoTable>
      <nameOfIssuer>TEST</nameOfIssuer><titleOfClass>COM</titleOfClass>
      <cusip>123456789</cusip>{field_xml}{shares}
    </infoTable></informationTable>
    """.encode()
    with pytest.raises(HoldingValidationError, match=field_name):
        parse_info_table(xml)


def test_unknown_shares_type_raises():
    xml = SAMPLE.replace(b"<sshPrnamtType>SH</sshPrnamtType>", b"<sshPrnamtType>UNIT</sshPrnamtType>", 1)
    with pytest.raises(HoldingValidationError, match="sshPrnamtType"):
        parse_info_table(xml)


def test_unknown_put_call_raises():
    xml = SAMPLE.replace(b"<putCall>PUT</putCall>", b"<putCall>OTHER</putCall>")
    with pytest.raises(HoldingValidationError, match="putCall"):
        parse_info_table(xml)


def test_amendment_with_both_types_is_rejected():
    xml = b"""<edgarSubmission><headerData><submissionType>13F-HR/A</submissionType></headerData>
    <formData><coverPage><reportCalendarOrQuarter>03-31-2026</reportCalendarOrQuarter>
    <isAmendment>true</isAmendment><amendmentNo>1</amendmentNo>
    <amendmentInfo><amendmentType>RESTATEMENT</amendmentType>
    <amendmentType>NEW HOLDINGS</amendmentType></amendmentInfo>
    </coverPage></formData></edgarSubmission>"""
    with pytest.raises(XmlParseError, match="exactly one amendment type"):
        parse_cover_page(xml)


def test_amendment_without_type_is_rejected():
    xml = b"""<edgarSubmission><headerData><submissionType>13F-HR/A</submissionType></headerData>
    <formData><coverPage><reportCalendarOrQuarter>03-31-2026</reportCalendarOrQuarter>
    <isAmendment>true</isAmendment><amendmentNo>1</amendmentNo>
    </coverPage></formData></edgarSubmission>"""
    with pytest.raises(XmlParseError, match="exactly one amendment type"):
        parse_cover_page(xml)


@pytest.mark.parametrize('payload', [b'<html>Access denied</html>', b'<informationTable/>'])
def test_non_holdings_documents_cannot_become_empty_portfolios(payload):
    with pytest.raises(XmlParseError):
        parse_info_table(payload)


def test_missing_identity_and_integer_overflow_are_rejected():
    for before, after in [
        (b'037833100', b''),
        (b'APPLE INC', b''),
        (b'<value>1000000</value>', b'<value>9223372036854775808</value>'),
    ]:
        with pytest.raises(HoldingValidationError):
            parse_info_table(SAMPLE.replace(before, after, 1))


def test_utf16_entity_declaration_is_rejected():
    payload = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY x "secret">]><informationTable/>'.encode('utf-16')
    with pytest.raises(XmlParseError, match='DTD|entity'):
        parse_info_table(payload)
