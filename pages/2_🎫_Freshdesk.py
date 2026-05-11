import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from app_lib import (
    FD_OPEN_STATUSES,
    FRESHDESK_PATH,
    apply_page_style,
    load_freshdesk,
    render_header,
)

apply_page_style("Freshdesk · Dashboard", icon="🎫")

if not os.path.exists(FRESHDESK_PATH):
    st.error(
        f"No se encontró `{os.path.basename(FRESHDESK_PATH)}`. "
        "Corré primero `python freshdesk_tickets.py` para generar el reporte."
    )
    st.stop()

fd_tickets, fd_entries = load_freshdesk(FRESHDESK_PATH, os.path.getmtime(FRESHDESK_PATH))

render_header(
    "🎫 Freshdesk Dashboard",
    report_path=FRESHDESK_PATH,
    refresh_scripts=["freshdesk_tickets.py"],
    button_key="refresh_freshdesk",
)

fd = fd_tickets.copy()
fd["is_open"] = fd["status"].isin(FD_OPEN_STATUSES)
today = pd.Timestamp(datetime.now().date())
end_ref = fd["resolved_at"].fillna(fd["closed_at"]).fillna(today)
fd["dias_abierta"] = (end_ref - fd["created_at"]).dt.days

st.subheader("KPIs")
total = len(fd)
opened = int(fd["is_open"].sum())
resolved = int(fd["resolved_at"].notna().sum())
escalated = int(fd["is_escalated"].sum())
total_h = float(fd["time_tracked_hours"].sum())
avg_h = total_h / total if total else 0.0

last_30 = today - pd.Timedelta(days=30)
created_30 = int((fd["created_at"] >= last_30).sum())
resolved_30 = int((fd["resolved_at"] >= last_30).sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Tickets totales", f"{total:,}")
k2.metric("Abiertos", f"{opened:,}")
k3.metric("Resueltos", f"{resolved:,}")
k4.metric("Escalados", f"{escalated:,}")

k5, k6, k7, k8 = st.columns(4)
k5.metric("Horas trackeadas", f"{total_h:,.1f}")
k6.metric("Prom. h/ticket", f"{avg_h:,.2f}")
k7.metric("Creados (30d)", f"{created_30:,}")
k8.metric("Resueltos (30d)", f"{resolved_30:,}")

st.divider()
st.subheader("Distribución")
g1, g2 = st.columns(2)
with g1:
    by_status = fd.groupby("status").size().reset_index(name="tickets")
    fig = px.pie(by_status, names="status", values="tickets", title="Tickets por status", hole=0.5)
    fig.update_layout(height=380)
    st.plotly_chart(fig, use_container_width=True)
with g2:
    by_pri = fd.groupby("priority").size().reset_index(name="tickets")
    fig = px.bar(
        by_pri,
        x="priority",
        y="tickets",
        text="tickets",
        title="Tickets por prioridad",
        color="priority",
        color_discrete_map={"Low": "#22c55e", "Medium": "#eab308", "High": "#f97316", "Urgent": "#ef4444"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=380, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

g3, g4 = st.columns(2)
with g3:
    by_source = fd.groupby("source").size().reset_index(name="tickets").sort_values("tickets", ascending=False)
    fig = px.bar(by_source, x="source", y="tickets", text="tickets", title="Tickets por canal")
    fig.update_traces(textposition="outside")
    fig.update_layout(height=380, xaxis_tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)
with g4:
    top_groups = (
        fd.groupby("group").size().sort_values(ascending=False).head(10).reset_index(name="tickets")
    )
    fig = px.bar(
        top_groups,
        x="tickets",
        y="group",
        text="tickets",
        orientation="h",
        title="Top grupos",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=380, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Agentes")
per_agent = (
    fd.groupby("agent")
    .agg(
        tickets=("ticket_id", "count"),
        horas=("time_tracked_hours", "sum"),
        resueltos=("resolved_at", lambda s: int(s.notna().sum())),
    )
    .reset_index()
    .sort_values("tickets", ascending=False)
)
per_agent["horas"] = per_agent["horas"].round(2)
per_agent["prom_h_ticket"] = (per_agent["horas"] / per_agent["tickets"]).round(2).fillna(0)

col_a, col_b = st.columns([2, 1])
with col_a:
    fig = px.bar(
        per_agent.head(15),
        x="agent",
        y="tickets",
        text="tickets",
        title="Tickets por agente (top 15)",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=420, xaxis_tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)
with col_b:
    st.dataframe(per_agent, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Tendencia y aging")
g5, g6 = st.columns(2)
with g5:
    monthly = pd.DataFrame(
        {
            "Creados": fd.groupby(fd["created_at"].dt.to_period("M")).size(),
            "Resueltos": fd[fd["resolved_at"].notna()]
            .groupby(fd[fd["resolved_at"].notna()]["resolved_at"].dt.to_period("M"))
            .size(),
        }
    ).fillna(0).astype(int)
    monthly.index = monthly.index.astype(str)
    monthly = monthly.reset_index().rename(columns={"index": "mes"}).melt(
        id_vars="mes", var_name="tipo", value_name="tickets"
    )
    fig = px.line(monthly, x="mes", y="tickets", color="tipo", markers=True, title="Creados vs resueltos por mes")
    fig.update_layout(height=380)
    st.plotly_chart(fig, use_container_width=True)
with g6:
    open_fd = fd[fd["is_open"]].copy()
    if not open_fd.empty:
        bins = [-1, 7, 30, 90, float("inf")]
        labels_ag = ["0-7 días", "7-30 días", "30-90 días", "+90 días"]
        open_fd["bucket"] = pd.cut(open_fd["dias_abierta"], bins=bins, labels=labels_ag)
        aging = (
            open_fd.groupby("bucket", observed=True)
            .size()
            .reindex(labels_ag, fill_value=0)
            .reset_index(name="tickets")
        )
        fig = px.bar(
            aging,
            x="bucket",
            y="tickets",
            text="tickets",
            title="Aging de tickets abiertos",
            color="bucket",
            color_discrete_sequence=["#22c55e", "#eab308", "#f97316", "#ef4444"],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(height=380, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay tickets abiertos.")

st.divider()
st.subheader("Detalle")
st.dataframe(
    fd.sort_values("created_at", ascending=False),
    use_container_width=True,
    hide_index=True,
)
