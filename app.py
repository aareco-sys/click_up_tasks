"""Home: elegir dashboard a ver (ClickUp o Freshdesk)."""
import os
from datetime import datetime

import streamlit as st

from app_lib import FRESHDESK_PATH, REPORT_PATH, apply_page_style

apply_page_style("Dashboards · Home", icon="🏠")


def _last_update(path: str) -> str:
    if not os.path.exists(path):
        return "—"
    mt = datetime.fromtimestamp(os.path.getmtime(path))
    return f"{mt.strftime('%d/%m/%Y')} · {mt.strftime('%H:%M')}"


st.markdown(
    """
    <style>
        .home-card {
            border: 1px solid rgba(120, 120, 130, 0.25);
            border-radius: 14px;
            padding: 1.5rem 1.5rem 1.2rem 1.5rem;
            background: rgba(120, 120, 130, 0.04);
            height: 100%;
        }
        .home-card h2 { margin: 0 0 0.3rem 0; font-size: 1.45rem; }
        .home-card .sub { color: #6b7280; font-size: 0.9rem; margin-bottom: 0.8rem; }
        .home-card ul { margin: 0 0 0.8rem 1.1rem; padding: 0; }
        .home-card li { font-size: 0.92rem; line-height: 1.55; }
        .home-card .stamp {
            font-size: 0.78rem; color: #6b7280; margin-top: 0.4rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏠 Dashboards")
st.caption("Elegí qué reporte querés ver. Cada dashboard tiene sus propios filtros y botón de actualización manual.")

col_cu, col_fd = st.columns(2, gap="large")

with col_cu:
    st.markdown(
        f"""
        <div class="home-card">
            <h2>📊 ClickUp</h2>
            <div class="sub">Tareas, horas trackeadas y aging por persona / lista / folder.</div>
            <ul>
                <li>Resumen y highlights del workspace</li>
                <li>Carga por persona y por status</li>
                <li>Detalle por folder y por lista</li>
                <li>Cuentas activas MSP</li>
            </ul>
            <div class="stamp">Última actualización: <strong>{_last_update(REPORT_PATH)}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_📊_ClickUp.py", label="Abrir ClickUp →", icon="📊")

with col_fd:
    st.markdown(
        f"""
        <div class="home-card">
            <h2>🎫 Freshdesk</h2>
            <div class="sub">Tickets, prioridades, agentes y tendencia mensual.</div>
            <ul>
                <li>KPIs (abiertos, resueltos, escalados)</li>
                <li>Distribución por prioridad, canal y grupo</li>
                <li>Carga por agente</li>
                <li>Aging de tickets abiertos</li>
            </ul>
            <div class="stamp">Última actualización: <strong>{_last_update(FRESHDESK_PATH)}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_🎫_Freshdesk.py", label="Abrir Freshdesk →", icon="🎫")

st.caption(
    "La actualización automática corre Lun-Vie de 09:00 a 18:00 (ART) vía launchd. "
    "También podés forzarla manualmente desde cada dashboard."
)
