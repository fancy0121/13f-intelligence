"""Deterministic economic-type classifier (outcome-blind, resolution-independent).

Implements the frozen rules of research/security_semantic_audit_protocol_v0.2.2.md
section 5. Inputs: 13F issuer + title_of_class + OpenFIGI records (cached).
"""

from __future__ import annotations

from thirteenf.research.semantic.taxonomy import (
    COMMON_TITLES,
    ClassificationResult,
    ClassificationStatus,
    EconomicType,
    is_pooled_issuer,
    title_has,
    _of_set,
)


def classify_cusip(
    cusip: str,
    issuer: str | None,
    title_of_class: str | None,
    of_records: list[dict],
) -> ClassificationResult:
    """Classify one CUSIP to an economic type per the frozen protocol."""
    title = title_of_class or ""
    pooled_issuer = is_pooled_issuer(issuer)
    of_types = _of_set(of_records, "securityType")
    of_sectors = _of_set(of_records, "marketSector")

    def result(etype, status, sources, reason):
        return ClassificationResult(
            cusip=cusip,
            economic_type=etype,
            classification_status=status,
            classification_sources=tuple(sources),
            classification_reason=reason,
        )

    # T1 / F1: non-equity
    if "Corp" in of_sectors:
        return result(
            EconomicType.NON_EQUITY_OR_UNSUPPORTED.value,
            ClassificationStatus.VERIFIED.value,
            ["openfigi"],
            "T1 marketSector=Corp",
        )
    if title_has(title, "NOTE") or "%" in title:
        return result(
            EconomicType.NON_EQUITY_OR_UNSUPPORTED.value,
            ClassificationStatus.PROVISIONAL.value,
            ["sec_title"],
            "F1 title NOTE",
        )

    # Explicit title markers (strong; C1 conflict when OpenFIGI disagrees)
    if title_has(title, "ETF"):
        if "ETP" in of_types or "Closed-End Fund" in of_types:
            status = ClassificationStatus.VERIFIED.value
        elif of_types:
            status = ClassificationStatus.CONFLICT.value
        else:
            status = ClassificationStatus.PROVISIONAL.value
        return result(
            EconomicType.ETF.value, status,
            ["sec_title"] + (["openfigi"] if "ETP" in of_types else []),
            "T2 title ETF",
        )
    if title_has(title, "ADR", "ADS"):
        if "ADR" in of_types:
            status = ClassificationStatus.VERIFIED.value
        elif of_types:
            status = ClassificationStatus.CONFLICT.value
        else:
            status = ClassificationStatus.PROVISIONAL.value
        return result(
            EconomicType.OPERATING_ADR.value, status,
            ["sec_title"] + (["openfigi"] if "ADR" in of_types else []),
            "T5 title ADR/ADS",
        )
    if title_has(title, "PFD"):
        return result(
            EconomicType.PREFERRED_OR_HYBRID.value,
            ClassificationStatus.VERIFIED.value if of_types else ClassificationStatus.PROVISIONAL.value,
            ["sec_title"] + (["openfigi"] if of_types else []),
            "T7 title PFD",
        )

    # OpenFIGI primary rules
    if of_types:
        if "ETP" in of_types:
            return result(EconomicType.ETF.value, ClassificationStatus.VERIFIED.value,
                          ["openfigi"], "T2 securityType=ETP")
        if "Closed-End Fund" in of_types:
            return result(EconomicType.CLOSED_END_FUND.value, ClassificationStatus.VERIFIED.value,
                          ["openfigi"], "T3 securityType=Closed-End Fund")
        if "Mutual Fund" in of_types or "Fund" in of_types:
            return result(EconomicType.MUTUAL_OR_POOLED_FUND.value, ClassificationStatus.VERIFIED.value,
                          ["openfigi"], "T4 securityType=Fund")
        if "ADR" in of_types:
            return result(EconomicType.OPERATING_ADR.value, ClassificationStatus.VERIFIED.value,
                          ["openfigi"], "T5 securityType=ADR")
        if "REIT" in of_types or "Royalty Trst" in of_types:
            return result(EconomicType.REIT_OR_SPECIAL_EQUITY.value, ClassificationStatus.VERIFIED.value,
                          ["openfigi"], "T6 securityType=REIT/Royalty")
        if "Preferred Stock" in of_types:
            return result(EconomicType.PREFERRED_OR_HYBRID.value, ClassificationStatus.VERIFIED.value,
                          ["openfigi"], "T7 securityType=Preferred Stock")
        if "Right" in of_types or "Warrant" in of_types:
            return result(EconomicType.OTHER_13F_SECURITY.value, ClassificationStatus.VERIFIED.value,
                          ["openfigi"], "T10 securityType=Right/Warrant")
        if "Common Stock" in of_types:
            if pooled_issuer and title:
                return result(
                    EconomicType.MUTUAL_OR_POOLED_FUND.value,
                    ClassificationStatus.PROVISIONAL.value,
                    ["openfigi", "issuer"],
                    "T8 Common Stock but pooled issuer",
                )
            return result(EconomicType.OPERATING_COMMON_EQUITY.value, ClassificationStatus.VERIFIED.value,
                          ["openfigi"], "T8 securityType=Common Stock")
        other = of_types & {"Unit", "Tracking Stk", "NY Reg Shrs", "Ltd Part", "MLP"}
        if other:
            if pooled_issuer:
                return result(EconomicType.MUTUAL_OR_POOLED_FUND.value,
                              ClassificationStatus.PROVISIONAL.value,
                              ["openfigi", "issuer"], "T9 pooled issuer")
            return result(EconomicType.OPERATING_OTHER_EQUITY.value,
                          ClassificationStatus.VERIFIED.value,
                          ["openfigi"], f"T9 securityType in {sorted(other)}")
        return result(EconomicType.OTHER_13F_SECURITY.value,
                      ClassificationStatus.PROVISIONAL.value,
                      ["openfigi"], f"other securityType {sorted(of_types)}")

    # Fallback heuristics (no usable OpenFIGI)
    if pooled_issuer:
        return result(EconomicType.MUTUAL_OR_POOLED_FUND.value,
                      ClassificationStatus.PROVISIONAL.value,
                      ["issuer"], "F4 pooled issuer")
    if title.upper() in COMMON_TITLES:
        return result(EconomicType.OPERATING_COMMON_EQUITY.value,
                      ClassificationStatus.PROVISIONAL.value,
                      ["sec_title"], "F5 common title")
    if title_has(title, "UNIT"):
        return result(EconomicType.OPERATING_OTHER_EQUITY.value,
                      ClassificationStatus.PROVISIONAL.value,
                      ["sec_title"], "F6 unit title")
    return result(EconomicType.UNKNOWN.value,
                  ClassificationStatus.UNKNOWN.value,
                  [], "F7 no evidence")

