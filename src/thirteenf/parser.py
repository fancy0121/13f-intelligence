"""Parse SEC 13F INFORMATION TABLE XML into normalized holding rows.

The XML is namespace-prefixed (`<n1:informationTable>` or default namespace);
all field access is namespace-agnostic via local-name XPath. Missing or
malformed fields are tolerated (set to None / empty) so that a single bad row
does not silently drop the whole filing; malformed XML raises XmlParseError.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree


class XmlParseError(ValueError):
    """Raised when the document cannot be parsed as XML."""


@dataclass(frozen=True)
class HoldingRow:
    row_ordinal: int
    name_of_issuer: str
    title_of_class: str
    cusip: str
    value: int | None
    shares: float | None
    put_call: str
    ssh_prnamt_type: str
    investment_discretion: str
    other_manager: str


def parse_info_table(xml_bytes: bytes) -> list[HoldingRow]:
    """Parse an INFORMATION TABLE XML document into HoldingRow objects."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        raise XmlParseError(f"malformed XML: {exc}") from exc

    rows: list[HoldingRow] = []
    info_tables = root.xpath(
        "//*[local-name()='infoTable' and "
        "ancestor::*[local-name()='informationTable']]"
    )
    if not info_tables:
        info_tables = root.xpath("//*[local-name()='infoTable']")

    for ordinal, node in enumerate(info_tables, start=1):
        text = lambda name: _child_text(node, name)  # noqa: E731
        value_text = text("value")
        shares_text = text("sshPrnamt")
        put_call = (text("putCall") or "").strip().upper()
        if put_call not in ("PUT", "CALL"):
            put_call = ""
        rows.append(
            HoldingRow(
                row_ordinal=ordinal,
                name_of_issuer=(text("nameOfIssuer") or "").strip(),
                title_of_class=(text("titleOfClass") or "").strip(),
                cusip=(text("cusip") or "").strip().upper(),
                value=_to_int(value_text),
                shares=_to_float(shares_text),
                put_call=put_call,
                ssh_prnamt_type=(text("sshPrnamtType") or "").strip(),
                investment_discretion=(text("investmentDiscretion") or "").strip(),
                other_manager=(text("otherManager") or "").strip(),
            )
        )
    return rows


def _child_text(node, local_name: str) -> str:
    # sshPrnamt / sshPrnamtType live inside <shrsOrPrnAmt>; other fields are
    # direct children. Descendant search handles both safely because we always
    # match on local-name (e.g. value vs votingAuthority/Sole never collide).
    children = node.xpath(f".//*[local-name()='{local_name}']")
    if not children:
        return ""
    return (children[0].text or "").strip()


def _to_int(text: str) -> int | None:
    text = text.replace(",", "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _to_float(text: str) -> float | None:
    text = text.replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
