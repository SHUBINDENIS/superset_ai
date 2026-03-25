import html
from datetime import datetime, timezone
from typing import Any

import streamlit as st


def apply_product_theme() -> None:
    st.markdown(
        """
        <style>
          :root {
            --brand-primary: #1266e3;
            --brand-accent: #0ea5a8;
            --brand-bg: #e7edf7;
            --brand-card: #ffffff;
            --brand-muted: #5b6478;
            --brand-border: #d2dced;
            --brand-shadow: rgba(21, 42, 74, 0.08);
          }
          [data-testid="stAppViewContainer"] {
            background:
              radial-gradient(1200px 420px at 92% -10%, rgba(18, 102, 227, 0.2), transparent 55%),
              radial-gradient(900px 360px at 5% -8%, rgba(14, 165, 168, 0.18), transparent 55%),
              linear-gradient(180deg, rgba(201, 214, 235, 0.36) 0%, rgba(231, 237, 247, 0.9) 18%, rgba(231, 237, 247, 1) 100%),
              var(--brand-bg);
          }
          [data-testid="block-container"] {
            padding-top: 1.3rem;
            padding-bottom: 1.8rem;
          }
          [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #2d4969 0%, #355779 52%, #3a5f84 100%);
            border-right: 1px solid rgba(241, 247, 255, 0.32);
          }
          [data-testid="stSidebar"] * {
            color: #f1f6ff !important;
          }
          [data-testid="stSidebar"] hr {
            border-color: rgba(241, 247, 255, 0.28);
          }
          .sidebar-brand {
            border-radius: 14px;
            padding: 12px 14px;
            margin: 2px 0 12px 0;
            border: 1px solid rgba(241, 247, 255, 0.34);
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.2) 0%, rgba(214, 232, 255, 0.12) 100%);
            box-shadow: 0 10px 24px rgba(24, 44, 74, 0.26);
            backdrop-filter: blur(2px);
          }
          .sidebar-brand h3 {
            margin: 0;
            font-size: 1.03rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            color: #f8fbff;
          }
          .sidebar-brand p {
            margin: 5px 0 0 0;
            font-size: 0.84rem;
            color: #dce8fb;
            opacity: 0.95;
          }
          .sidebar-section {
            margin: 3px 0 8px 0;
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #d6e6ff;
            opacity: 0.95;
            font-weight: 700;
          }
          [data-testid="stSidebar"] button[kind="secondary"] {
            border: 1px solid rgba(241, 247, 255, 0.25) !important;
            background: rgba(233, 244, 255, 0.16) !important;
            border-radius: 12px !important;
            color: #f6fbff !important;
            box-shadow: 0 4px 12px rgba(16, 34, 59, 0.15);
          }
          [data-testid="stSidebar"] button[kind="secondary"]:hover {
            border-color: rgba(241, 247, 255, 0.6) !important;
            background: rgba(233, 244, 255, 0.26) !important;
          }
          [data-testid="stSidebar"] button[kind="primary"] {
            border: 1px solid rgba(255, 255, 255, 0.45) !important;
            background: linear-gradient(135deg, #7ab2ff 0%, #5b95ee 100%) !important;
            color: #ffffff !important;
            border-radius: 12px !important;
            box-shadow: 0 7px 16px rgba(15, 38, 69, 0.24);
          }
          [data-testid="stSidebar"] button[kind="primary"]:hover {
            filter: brightness(1.03);
          }
          [data-testid="stSidebar"] [data-testid="stAlert"] {
            border-radius: 12px;
          }
          .hero {
            border-radius: 18px;
            padding: 22px 24px;
            background: linear-gradient(120deg, #0f4db8 0%, #0a8ea8 100%);
            color: #ffffff;
            margin-bottom: 14px;
            box-shadow: 0 14px 32px rgba(14, 43, 95, 0.22);
          }
          .hero h2 {
            margin: 0 0 6px 0;
            font-size: 1.5rem;
            font-weight: 700;
          }
          .hero p {
            margin: 0;
            opacity: 0.94;
            font-size: 0.98rem;
          }
          .section-title {
            font-weight: 700;
            margin-top: 8px;
            margin-bottom: 8px;
            color: #0f172a;
          }
          .hint {
            color: var(--brand-muted);
            font-size: 0.9rem;
          }
          .kpi-card {
            border: 1px solid var(--brand-border);
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(247, 250, 255, 0.98) 100%);
            border-radius: 14px;
            padding: 12px 14px;
            margin: 6px 0 10px 0;
            box-shadow: 0 8px 18px var(--brand-shadow);
          }
          .kpi-label {
            color: var(--brand-muted);
            font-size: 0.82rem;
            margin-bottom: 2px;
          }
          .kpi-value {
            color: #0f172a;
            font-size: 1.25rem;
            font-weight: 700;
            line-height: 1.2;
          }
          .kpi-meta {
            color: var(--brand-muted);
            font-size: 0.8rem;
            margin-top: 4px;
          }
          .empty-state {
            border: 1px dashed #aebed9;
            background: rgba(255, 255, 255, 0.72);
            border-radius: 14px;
            padding: 16px;
            margin: 8px 0 10px 0;
          }
          .empty-state h4 {
            margin: 0 0 4px 0;
            color: #0f172a;
            font-size: 1rem;
          }
          .empty-state p {
            margin: 0;
            color: var(--brand-muted);
            font-size: 0.92rem;
          }
          [data-testid="stDataFrame"] {
            border: 1px solid var(--brand-border);
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 10px 22px var(--brand-shadow);
            background: #ffffff;
          }
          [data-testid="stDataFrame"] iframe {
            border-radius: 14px;
          }
          [data-testid="stTextInput"], [data-testid="stTextArea"], [data-testid="stSelectbox"], [data-testid="stMultiSelect"], [data-testid="stNumberInput"] {
            margin-bottom: 2px;
          }
          [data-testid="stForm"] {
            border: 1px solid #d9e2f1;
            border-radius: 14px;
            padding: 14px;
            background: rgba(255, 255, 255, 0.94);
            box-shadow: 0 8px 18px var(--brand-shadow);
          }
          div.stButton > button[kind] {
            border-radius: 10px;
            border: 1px solid #c6d4ea;
            box-shadow: 0 4px 10px rgba(25, 50, 92, 0.06);
          }
          div.stButton > button[kind]:hover {
            border-color: #7aa2e8;
          }
          [data-testid="stChatMessage"] {
            border-radius: 14px;
            padding: 2px 6px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_message(role: str, content: str) -> None:
    with st.chat_message(role):
        st.write(content)


def parse_examples_input(raw: str):
    return parse_simple_csv(raw)


def parse_simple_csv(raw: str):
    if not raw:
        return []
    tokens = [item.strip() for item in raw.replace("\n", ",").split(",")]
    return [item for item in tokens if item]


def render_kpi_cards(items: list[dict[str, Any]], max_columns: int = 4) -> None:
    cards = [item for item in items if isinstance(item, dict)]
    if not cards:
        return

    max_columns = max(1, int(max_columns))
    for start in range(0, len(cards), max_columns):
        chunk = cards[start : start + max_columns]
        cols = st.columns(len(chunk))
        for col, item in zip(cols, chunk):
            with col:
                label = html.escape(str(item.get("label", "")).strip())
                value = html.escape(str(item.get("value", "")).strip())
                meta_raw = str(item.get("meta", "")).strip()
                meta = html.escape(meta_raw) if meta_raw else ""
                meta_block = f"<div class='kpi-meta'>{meta}</div>" if meta else ""
                st.markdown(
                    f"""
                    <div class="kpi-card">
                      <div class="kpi-label">{label}</div>
                      <div class="kpi-value">{value}</div>
                      {meta_block}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def render_empty_state(title: str, description: str) -> None:
    safe_title = html.escape(str(title))
    safe_desc = html.escape(str(description))
    st.markdown(
        f"""
        <div class="empty-state">
          <h4>{safe_title}</h4>
          <p>{safe_desc}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_iso_utc(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return raw
