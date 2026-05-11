"""Helpers compartidos entre el home (app.py) y las páginas de pages/."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

# ── Paths / constantes ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(BASE_DIR, "clickup_tasks_report.xlsx")
FRESHDESK_PATH = os.path.join(BASE_DIR, "freshdesk_tickets_report.xlsx")

FD_OPEN_STATUSES = {"Open", "Pending", "Waiting on Customer", "Waiting on Third Party"}

MSP_SHEET_ID = os.getenv(
    "GOOGLE_SHEET_MSP_ID", "1hXFpjrIlqLPrPechmPtYJUa41Cn0JuVS_W-Rz5gAIBg"
)
MSP_TRUE_VALUES = {"si", "sí", "yes", "true", "1", "x"}

ALL_OPTION = "✓ Ver todos"


def apply_page_style(title: str, icon: str = "📊") -> None:
    """st.set_page_config + estilos comunes. Llamar al inicio de cada página."""
    st.set_page_config(
        page_title=title,
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
            .block-container { padding-top: 2rem; padding-bottom: 2rem; }
            [data-testid="stMetricValue"] { font-size: 2rem; }
            h1, h2, h3 { letter-spacing: -0.02em; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Loaders cacheados ──────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_clickup(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_excel(path)

    for col in ("date_created", "date_closed"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "assignees" not in df.columns:
        df["assignees"] = "Sin asignar"
    df["assignees"] = df["assignees"].fillna("Sin asignar").replace("", "Sin asignar")

    if "time_tracked_hours" in df.columns:
        df["time_tracked_hours"] = pd.to_numeric(
            df["time_tracked_hours"], errors="coerce"
        ).fillna(0.0)
    else:
        df["time_tracked_hours"] = 0.0

    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_msp_accounts(sheet_id: str) -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    df = pd.read_csv(url)
    if df.shape[1] < 4:
        return pd.DataFrame()
    msp_col = df.columns[3]
    mask = df[msp_col].astype(str).str.strip().str.lower().isin(MSP_TRUE_VALUES)
    return df[mask].iloc[:, :3].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_freshdesk(path: str, mtime: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    tickets = pd.read_excel(path, sheet_name="tickets")
    entries = pd.read_excel(path, sheet_name="time_entries")

    for col in ("created_at", "updated_at", "resolved_at", "closed_at", "first_responded_at"):
        if col in tickets.columns:
            tickets[col] = pd.to_datetime(tickets[col], errors="coerce")
    if "time_tracked_hours" in tickets.columns:
        tickets["time_tracked_hours"] = pd.to_numeric(
            tickets["time_tracked_hours"], errors="coerce"
        ).fillna(0.0)
    for col in ("agent", "group", "company", "agent_email"):
        if col in tickets.columns:
            tickets[col] = tickets[col].fillna("").replace(
                "", "Sin asignar" if col == "agent" else ""
            )

    for col in ("executed_at", "created_at", "updated_at"):
        if col in entries.columns:
            entries[col] = pd.to_datetime(entries[col], errors="coerce")
    if "hours" in entries.columns:
        entries["hours"] = pd.to_numeric(entries["hours"], errors="coerce").fillna(0.0)

    return tickets, entries


def explode_assignees(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["assignee"] = out["assignees"].str.split(", ")
    out = out.explode("assignee")
    out["assignee"] = out["assignee"].fillna("Sin asignar").replace("", "Sin asignar")
    return out


# ── Header con fecha de última actualización + botón de refresh ────────────────
def _run_scripts(scripts: list[str]) -> tuple[bool, str]:
    """Corre cada script con python y devuelve (ok_global, output_combinado)."""
    outputs: list[str] = []
    overall_ok = True
    for script in scripts:
        proc = subprocess.run(
            [sys.executable, script],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        ok = proc.returncode == 0
        overall_ok = overall_ok and ok
        tag = "OK" if ok else f"FAIL (rc={proc.returncode})"
        body = proc.stdout if ok else (proc.stderr or proc.stdout)
        outputs.append(f"--- {script} · {tag} ---\n{body[-800:]}")
    return overall_ok, "\n\n".join(outputs)


def render_header(
    title: str,
    report_path: str | None,
    refresh_scripts: list[str],
    button_key: str,
) -> None:
    """Renderiza el título + 'Última actualización' + botón 🔄 en el tope.

    - `report_path`: archivo cuyo mtime se muestra como última actualización.
      Si es None o no existe, se omite la fecha.
    - `refresh_scripts`: scripts a invocar cuando se clickea el botón.
    """
    mtime_str = None
    if report_path and os.path.exists(report_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(report_path))
        mtime_str = f"{mtime.strftime('%d/%m/%Y')} &nbsp; {mtime.strftime('%H:%M')}"

    head_left, head_info, head_btn = st.columns([6, 2, 1], vertical_alignment="center")
    with head_left:
        st.title(title)
    with head_info:
        if mtime_str:
            st.markdown(
                f"""
                <div style="text-align: right; line-height: 1.25;">
                    <div style="font-size: 0.75rem; color: #6b7280;">Última actualización</div>
                    <div style="font-size: 0.95rem; font-weight: 600;">{mtime_str}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with head_btn:
        clicked = st.button(
            "🔄",
            key=button_key,
            help=f"Forzar actualización ahora ({', '.join(refresh_scripts)})",
        )

    if clicked:
        with st.spinner("Actualizando datos… puede tardar un par de minutos"):
            ok, output = _run_scripts(refresh_scripts)
        if ok:
            st.success("Reporte actualizado")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Falló la actualización")
            st.code(output)
