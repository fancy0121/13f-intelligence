"""Shared ProductStore for the Streamlit UI (evidence only)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from thirteenf.product.evidence import ProductStore

ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource
def get_store() -> ProductStore:
    return ProductStore(
        ROOT / "data" / "thirteenf.db",
        ROOT / "reports" / "research" / "security_resolution_master.csv",
        ROOT / "reports" / "research" / "security_semantic_classification.csv",
        ROOT / "config" / "managers.csv",
    )

