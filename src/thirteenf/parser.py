"""Hardened parsers for SEC Form 13F XML components.

The cover page determines amendment semantics. The INFORMATION TABLE parser
preserves every reported row and validates fields that drive deterministic
analytics. XML namespaces are handled by local name because SEC schema
versions use different namespace URIs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from lxml import etree


_UNSAFE_XML_DECLARATION = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_NONNEGATIVE_INTEGER = re.compile(r"^(?:0|[1-9][0-9]*)$")


class XmlParseError(ValueError):
    """Raised when an XML component is unsafe, malformed, or contradictory."""


class HoldingValidationError(XmlParseError):
    """Raised when a holding row cannot safely feed numeric analysis."""

    def __init__(self, row_ordinal: int, field: str, value: str) -> None:
        self.row_ordinal = row_ordinal
        self.field = field
        self.value = value
        shown = value if value else "<missing>"
        super().__init__(
            f"holding row {row_ordinal}: invalid {field} value {shown!r}"
        )


class AmendmentType(str, Enum):
    """Normalized SEC amendment semantics used by the effective-state engine."""

    RESTATEMENT = "RESTATEMENT"
    ADD_NEW_HOLDINGS = "ADD_NEW_HOLDINGS"


@dataclass(frozen=True)
class CoverMetadata:
    report_period: str
    amendment_number: int | None
    amendment_type: AmendmentType | None


@dataclass(frozen=True)
class HoldingRow:
    row_ordinal: int
    name_of_issuer: str
    title_of_class: str
    cusip: str
    value: int
    shares: int
    put_call: str
    ssh_prnamt_type: str
    investment_discretion: str
    other_manager: str


def _safe_parser() -> etree.XMLParser:
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        recover=False,
        huge_tree=False,
    )


def _parse_xml(xml_bytes: bytes):
    if _UNSAFE_XML_DECLARATION.search(xml_bytes):
        raise XmlParseError("DTD and entity declarations are not allowed")
    try:
        return etree.fromstring(xml_bytes, parser=_safe_parser())
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise XmlParseError(f"malformed XML: {exc}") from exc


def parse_cover_page(xml_bytes: bytes) -> CoverMetadata:
    """Parse report period and amendment semantics from a 13F primary document."""

    root = _parse_xml(xml_bytes)
    submission_type = _first_text(root, "submissionType").upper()
    report_text = _first_text(root, "reportCalendarOrQuarter")
    if not report_text:
        raise XmlParseError("cover page is missing reportCalendarOrQuarter")
    report_period = _normalize_report_period(report_text)

    is_amendment_text = _first_text(root, "isAmendment").lower()
    if is_amendment_text not in {"true", "false"}:
        raise XmlParseError("cover page has invalid or missing isAmendment")
    is_amendment = is_amendment_text == "true"
    form_is_amendment = submission_type.endswith("/A")
    if form_is_amendment != is_amendment:
        raise XmlParseError(
            "submissionType and isAmendment provide contradictory amendment status"
        )

    amendment_type_nodes = root.xpath("//*[local-name()='amendmentType']")
    amendment_number_text = _first_text(root, "amendmentNo")
    if not is_amendment:
        if amendment_number_text or amendment_type_nodes:
            raise XmlParseError("non-amendment cover contains amendment metadata")
        return CoverMetadata(report_period, None, None)

    if len(amendment_type_nodes) != 1:
        raise XmlParseError("amendment must contain exactly one amendment type")
    if not _NONNEGATIVE_INTEGER.fullmatch(amendment_number_text):
        raise XmlParseError("amendment has invalid or missing amendmentNo")
    amendment_number = int(amendment_number_text)
    if amendment_number < 1:
        raise XmlParseError("amendmentNo must be at least 1")

    raw_type = (amendment_type_nodes[0].text or "").strip().upper()
    if raw_type == "RESTATEMENT":
        amendment_type = AmendmentType.RESTATEMENT
    elif raw_type == "NEW HOLDINGS":
        amendment_type = AmendmentType.ADD_NEW_HOLDINGS
    else:
        raise XmlParseError(f"unsupported amendmentType {raw_type!r}")
    return CoverMetadata(report_period, amendment_number, amendment_type)


def parse_info_table(xml_bytes: bytes) -> list[HoldingRow]:
    """Parse and validate an INFORMATION TABLE into lossless row identities."""

    root = _parse_xml(xml_bytes)
    rows: list[HoldingRow] = []
    info_tables = root.xpath(
        "//*[local-name()='infoTable' and "
        "ancestor::*[local-name()='informationTable']]"
    )
    if not info_tables:
        info_tables = root.xpath("//*[local-name()='infoTable']")

    for ordinal, node in enumerate(info_tables, start=1):
        text = lambda name: _child_text(node, name)  # noqa: E731
        put_call = text("putCall").upper()
        if put_call not in {"", "PUT", "CALL"}:
            raise HoldingValidationError(ordinal, "putCall", put_call)
        shares_type = text("sshPrnamtType").upper()
        if shares_type not in {"SH", "PRN"}:
            raise HoldingValidationError(ordinal, "sshPrnamtType", shares_type)
        rows.append(
            HoldingRow(
                row_ordinal=ordinal,
                name_of_issuer=text("nameOfIssuer"),
                title_of_class=text("titleOfClass"),
                cusip=text("cusip").upper(),
                value=_required_nonnegative_int(text("value"), ordinal, "value"),
                shares=_required_nonnegative_int(
                    text("sshPrnamt"), ordinal, "shares"
                ),
                put_call=put_call,
                ssh_prnamt_type=shares_type,
                investment_discretion=text("investmentDiscretion"),
                other_manager=text("otherManager"),
            )
        )
    return rows


def _first_text(node, local_name: str) -> str:
    matches = node.xpath(f"//*[local-name()='{local_name}']")
    if not matches:
        return ""
    return (matches[0].text or "").strip()


def _child_text(node, local_name: str) -> str:
    matches = node.xpath(f".//*[local-name()='{local_name}']")
    if not matches:
        return ""
    return (matches[0].text or "").strip()


def _required_nonnegative_int(text: str, row_ordinal: int, field: str) -> int:
    normalized = text.strip()
    if not _NONNEGATIVE_INTEGER.fullmatch(normalized):
        raise HoldingValidationError(row_ordinal, field, text)
    return int(normalized)


def _normalize_report_period(value: str) -> str:
    for format_string in ("%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, format_string).date().isoformat()
        except ValueError:
            continue
    raise XmlParseError(f"invalid reportCalendarOrQuarter {value!r}")
