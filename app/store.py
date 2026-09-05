"""Shared ProductStore for the Streamlit UI (evidence only)."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from thirteenf.product.evidence import ProductStore

ROOT = Path(__file__).resolve().parents[1]


def configured_database_path() -> Path:
    return Path(
        os.environ.get("THIRTEENF_DB_PATH", ROOT / "data" / "thirteenf.db")
    )


@st.cache_resource
def get_store() -> ProductStore:
    return ProductStore(
        configured_database_path(),
        Path(
            os.environ.get(
                "THIRTEENF_RESOLUTION_CSV",
                ROOT / "reports" / "research" / "security_resolution_master.csv",
            )
        ),
        Path(
            os.environ.get(
                "THIRTEENF_SEMANTIC_CSV",
                ROOT / "reports" / "research" / "security_semantic_classification.csv",
            )
        ),
        Path(
            os.environ.get(
                "THIRTEENF_MANAGERS_CSV",
                ROOT / "config" / "managers.csv",
            )
        ),
        methodology_version=os.environ.get("THIRTEENF_METHODOLOGY_VERSION"),
    )
