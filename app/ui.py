"""Shared UI helpers: bilingual labels, global styling, searchable selects.

Evidence-only: this module never computes or alters data; it only formats
labels and widgets for the Streamlit frontend.
"""

from __future__ import annotations

import streamlit as st


def T(zh: str, en: str) -> str:
    """Bilingual label: Chinese first, English after a slash."""
    return f"{zh} / {en}"


def B(zh: str, en: str) -> str:
    """Bilingual sentence joined with a full stop, for longer captions."""
    return f"{zh}。{en}."


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
  (up to 45-day disclosure lag). 仅展示证据，不含投资建议；报告季度 ≠ 实时持仓（最长 45 天披露延迟）。
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

    query = st.text_input(
        label,
        key=f"{key}_q",
        placeholder=T("输入关键字筛选…", "Type to filter…"),
        help=help_text,
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
