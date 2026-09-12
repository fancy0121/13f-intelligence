"""Shared UI helpers: bilingual labels, global styling, searchable selects.

Evidence-only: this module never computes or alters data; it only formats
labels and widgets for the Streamlit frontend.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_NAMES_PATH = ROOT / "config" / "display_names.csv"


def T(zh: str, en: str) -> str:
    """Bilingual label: Chinese first, English after a slash."""
    return f"{zh} / {en}"


def B(zh: str, en: str) -> str:
    """Bilingual sentence joined with a full stop, for longer captions."""
    zh_text = zh.rstrip()
    en_text = en.rstrip()
    if not zh_text.endswith(("。", "！", "？")):
        zh_text += "。"
    if not en_text.endswith((".", "!", "?")):
        en_text += "."
    return f"{zh_text}{en_text}"


@lru_cache(maxsize=1)
def _display_names() -> dict[tuple[str, str], dict[str, str]]:
    """Load presentation-only names; SEC English names remain authoritative."""
    if not DISPLAY_NAMES_PATH.exists():
        return {}
    with DISPLAY_NAMES_PATH.open(encoding="utf-8-sig", newline="") as fh:
        return {
            (row["entity_type"].strip(), row["entity_key"].strip().upper()): row
            for row in csv.DictReader(fh)
            if row.get("entity_type") and row.get("entity_key")
        }


def display_entity_name(entity_type: str, entity_key: str, english_name: str | None) -> str:
    """Return an honest bilingual name without altering identity facts."""
    english = (english_name or "").strip() or T("英文名缺失", "English name missing")
    row = _display_names().get((entity_type.strip(), entity_key.strip().upper()))
    chinese = ""
    if row and row.get("status", "").strip() == "PROJECT_CURATED":
        chinese = row.get("name_zh", "").strip()
    return f"{chinese or '中文名待核验'} / {english}"


def display_manager_name(english_name: str) -> str:
    return display_entity_name("manager", english_name, english_name)


def display_security_name(cusip: str, english_name: str | None) -> str:
    return display_entity_name("security", cusip, english_name)


def display_name_keys(entity_type: str, query: str) -> list[str]:
    """Return curated entity keys matching a Chinese display-name query."""
    needle = (query or "").strip().casefold()
    if not needle:
        return []
    return [
        row["entity_key"].strip()
        for (kind, _), row in _display_names().items()
        if kind == entity_type
        and row.get("status", "").strip() == "PROJECT_CURATED"
        and needle in row.get("name_zh", "").casefold()
    ]


def security_search_with_display_names(store, query: str) -> list[dict]:
    """Search SEC identity fields plus curated Chinese display aliases."""
    matches = list(store.security_search(query))
    seen = {m["cusip"] for m in matches}
    for cusip in display_name_keys("security", query):
        for match in store.security_search(cusip):
            if match["cusip"] not in seen:
                matches.append(match)
                seen.add(match["cusip"])
    return matches


def security_option_label(match: dict) -> str:
    ticker = match.get("ticker") or T("代码未解析", "Ticker unresolved")
    share_class = match.get("share_class") or T("类别未收录", "Class unavailable")
    return (
        f"{display_security_name(match['cusip'], match.get('issuer'))} · "
        f"{ticker} · {match['cusip']} · {share_class}"
    )


_CODE_LABELS = {
    "NEW": ("新增", "NEW"),
    "ADD": ("增持", "ADD"),
    "REDUCE": ("减持", "REDUCE"),
    "EXIT": ("退出", "EXIT"),
    "UNCHANGED": ("未变化", "UNCHANGED"),
    "VERIFIED": ("已验证", "Verified"),
    "VERIFIED_WITH_SCOPE": ("限定范围已验证", "Verified with scope"),
    "VERIFIED_EXACT": ("精确验证", "Verified exact"),
    "VERIFIED_MULTI_SOURCE": ("多来源验证", "Verified by multiple sources"),
    "VERIFIED_HISTORICAL": ("历史验证", "Historically verified"),
    "PROVISIONAL": ("暂定", "Provisional"),
    "UNRESOLVED": ("未解析", "Unresolved"),
    "AMBIGUOUS": ("有歧义", "Ambiguous"),
    "CONFLICT": ("有冲突", "Conflict"),
    "NON_EQUITY_OR_UNSUPPORTED": ("非股权或暂不支持", "Non-equity or unsupported"),
    "UNKNOWN": ("未知", "Unknown"),
    "OPERATING_COMMON_EQUITY": ("经营性普通股", "Operating common equity"),
    "OPERATING_ADR": ("经营性公司存托凭证", "Operating-company ADR"),
    "OPERATING_OTHER_EQUITY": ("其他经营性股权", "Other operating equity"),
    "ETF": ("交易所交易基金", "ETF"),
    "MUTUAL_OR_POOLED_FUND": ("共同或集合基金", "Mutual or pooled fund"),
    "CLOSED_END_FUND": ("封闭式基金", "Closed-end fund"),
    "REIT_OR_SPECIAL_EQUITY": ("房地产信托或特殊股权", "REIT or special equity"),
    "OTHER_13F_SECURITY": ("其他 13F 证券", "Other 13F security"),
    "PREFERRED_OR_HYBRID": ("优先或混合证券", "Preferred or hybrid security"),
    "INSUFFICIENT_DATA": ("数据不足", "Insufficient data"),
    "INSUFFICIENT_COMPARISON": ("缺少可比季度", "Insufficient comparison"),
    "MISSING_HISTORICAL_COMPARISON": ("缺少历史比较数据", "Missing historical comparison"),
    "LOW_BREADTH": ("覆盖面较低", "Low breadth"),
    "NO_RECENT_CHANGE": ("近期无变化", "No recent change"),
    "MIXED_ACTIVITY": ("增减并存", "Mixed activity"),
    "MORE_ADDS_THAN_REDUCTIONS": ("增持多于减持", "More adds than reductions"),
    "MORE_REDUCTIONS_THAN_ADDS": ("减持多于增持", "More reductions than adds"),
    "INCOMPLETE_QUARTER": ("季度不完整", "Incomplete quarter"),
    "SOURCE_QUARANTINED": ("源数据隔离", "Source quarantined"),
    "STALE_FILING": ("披露陈旧", "Stale filing"),
    "UNRESOLVED_CUSIP": ("CUSIP 未解析", "Unresolved CUSIP"),
    "FAILED_INGESTION": ("采集失败", "Failed ingestion"),
    "MALFORMED_FILING": ("披露文件格式异常", "Malformed filing"),
    "OK": ("正常", "OK"),
    "SETUP_REQUIRED": ("需要设置", "Setup required"),
    "NONE": ("无风险", "None"),
    "LOW": ("低风险", "Low"),
    "MODERATE": ("中等风险", "Moderate"),
    "HIGH": ("高风险", "High"),
    "PENDING": ("待完成", "Pending"),
}


def display_code(code: str | None, *, include_raw: bool = True) -> str:
    """Translate a governed code; optionally retain its raw value for audit views."""
    raw = (code or "UNKNOWN").strip().upper()
    label = _CODE_LABELS.get(raw)
    if label is None:
        return f"{T('未翻译状态', 'Untranslated status')} [{raw}]"
    zh, en = label
    if en == raw or not include_raw:
        return T(zh, en)
    return f"{T(zh, en)} [{raw}]"


BRAND_HTML = """
<div style="padding:.4rem .2rem 1rem;">
  <div style="font-size:1.3rem;font-weight:800;color:#FFFFFF;letter-spacing:.4px;">📊 13F Evidence</div>
  <div style="font-size:.78rem;color:#A9C7DE;margin-top:2px;">Institutional Intelligence · 机构持仓情报</div>
</div>
"""


FOOTER_HTML = """
<div style="margin-top:2.5rem;padding:1rem 1.2rem;border-top:1px solid #E3EAF2;
            color:#5B7186;font-size:.8rem;line-height:1.6;">
  <b>13F Institutional Evidence System · v0.5.1</b> ｜
  Source: SEC EDGAR original 13F disclosures · 数据来源：SEC EDGAR 原始 13F 披露<br/>
  Evidence only, no investment advice. Report quarter ≠ real-time holdings
  (normally filed within 45 days after quarter-end; amendments and confidential treatment may delay disclosure further).
  仅展示证据，不含投资建议；报告通常在季末后 45 天内提交，修订及保密处理可能使披露更晚。<br/>
  中文名称仅用于界面阅读，SEC 英文法定名与 CUSIP 仍是身份依据；未核验中文名会明确标记。
  Chinese names are display aids only; SEC legal names and CUSIPs remain authoritative.
</div>
"""


_CSS = """
<style>
:root {
  --brand:#0B2E4F; --brand2:#123F63; --accent:#1F7A8C; --accent-soft:#E1F5F4;
  --bg:#F4F7FB; --card:#FFFFFF; --text:#173042; --muted:#5B7186;
  --border:#E3EAF2; --ok:#1F9D55; --warn:#C05621; --bad:#C53030;
}
.stApp {
  background: linear-gradient(180deg, #F7FAFD 0%, #EEF3F9 100%);
  color: var(--text);
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC",
               "Noto Sans SC", "Helvetica Neue", Arial, sans-serif;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { padding-top: 1.6rem; max-width: 1200px; }

/* Sidebar */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--brand) 0%, var(--brand2) 100%);
  color: #EAF2F9;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color:#EAF2F9; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#EAF2F9; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.15); }

/* Headings */
h1, h2, h3 { color: var(--brand) !important; font-weight: 700 !important; }
h1 { font-size: 1.9rem !important; letter-spacing: .3px; }
h2 { font-size: 1.35rem !important; }
h3 { font-size: 1.12rem !important; }

/* Metric cards */
[data-testid="stMetric"] {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 14px 16px;
  box-shadow: 0 1px 3px rgba(11,46,79,.06);
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: .82rem !important; }
[data-testid="stMetricValue"] { color: var(--brand) !important; font-size: 1.35rem !important; font-weight: 700 !important; }

/* Buttons */
.stButton > button {
  background: var(--brand); color: #fff; border: none; border-radius: 10px;
  padding: .45rem 1rem; font-weight: 600; transition: all .15s ease;
}
.stButton > button:hover { background: var(--accent); color: #fff; }
.stButton > button[kind="secondary"] { background:#fff; color: var(--brand); border:1px solid var(--border); }
.stButton > button[kind="secondary"]:hover { background: var(--accent-soft); }

/* Text inputs */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
  border-radius: 10px; border: 1px solid var(--border);
}
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
  border-color: var(--accent); box-shadow: 0 0 0 2px rgba(31,122,140,.15);
}

/* Expander */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important; border-radius: 12px !important;
  background: var(--card);
}

/* Dataframe */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
[data-testid="stDataFrame"] thead th { background: #EEF4FA !important; color: var(--brand) !important; font-weight: 600 !important; }

/* Alerts */
[data-testid="stAlert"] { border-radius: 12px; }

/* Tabs */
[data-testid="stTabs"] [data-baseweb="tab"] { font-weight: 600; }

/* Captions */
[data-testid="stCaptionContainer"] { color: var(--muted); }
hr { border-color: var(--border); }
</style>
"""


def inject_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def searchable_select(
    label: str,
    options: list[str],
    key: str,
    help_text: str | None = None,
    max_options: int = 40,
) -> str | None:
    """Type-to-filter selection that supports keyboard input.

    Replaces st.selectbox (which cannot be typed into). Renders a text input
    plus clickable candidate buttons. Returns the selected option or None.
    """
    sel_key = f"{key}_sel"
    if sel_key not in st.session_state:
        st.session_state[sel_key] = None

    def commit_unique_match() -> None:
        typed = str(st.session_state.get(f"{key}_q", "")).strip().casefold()
        if not typed:
            return
        exact = [o for o in options if o.casefold() == typed]
        filtered_options = [o for o in options if typed in o.casefold()]
        if len(exact) == 1:
            st.session_state[sel_key] = exact[0]
        elif len(filtered_options) == 1:
            st.session_state[sel_key] = filtered_options[0]

    query = st.text_input(
        label,
        key=f"{key}_q",
        placeholder=T("输入关键字筛选…", "Type to filter…"),
        help=help_text,
        on_change=commit_unique_match,
    ).strip().lower()

    filtered = [o for o in options if query in o.lower()] if query else list(options)
    selected = st.session_state[sel_key]
    if selected is not None and selected not in filtered:
        st.session_state[sel_key] = None
        selected = None

    if not filtered:
        st.caption(T("无匹配选项，请调整关键字", "No matching option, adjust your keyword"))
        return selected

    if selected is not None:
        st.caption(f"✅ {T('已选择', 'Selected')}: **{selected}** — "
                   f"{T('如需更换，请继续输入并点击其他选项', 'type more and click another option to change')}")

    show = filtered[:max_options]
    cols = st.columns(2)
    for i, opt in enumerate(show):
        if st.button(opt, key=f"{key}_opt_{i}"):
            st.session_state[sel_key] = opt
    if len(filtered) > max_options:
        st.caption(
            T(
                f"仅显示前 {max_options} 个匹配（共 {len(filtered)} 个），请继续输入缩小范围",
                f"Showing first {max_options} of {len(filtered)}; keep typing to narrow",
            )
        )
    return st.session_state[sel_key]
