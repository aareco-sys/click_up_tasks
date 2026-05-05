import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

REPORT_PATH = "clickup_tasks_report.xlsx"

st.set_page_config(
    page_title="ClickUp Dashboard",
    page_icon="📊",
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


@st.cache_data(show_spinner=False)
def load_data(path: str, mtime: float) -> pd.DataFrame:
    df = pd.read_excel(path)

    for col in ("date_created", "date_closed"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "assignees" not in df.columns:
        df["assignees"] = "Sin asignar"
    df["assignees"] = df["assignees"].fillna("Sin asignar").replace("", "Sin asignar")

    if "time_tracked_hours" in df.columns:
        df["time_tracked_hours"] = pd.to_numeric(df["time_tracked_hours"], errors="coerce").fillna(0.0)
    else:
        df["time_tracked_hours"] = 0.0

    return df


def explode_assignees(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["assignee"] = out["assignees"].str.split(", ")
    out = out.explode("assignee")
    out["assignee"] = out["assignee"].fillna("Sin asignar").replace("", "Sin asignar")
    return out


if not os.path.exists(REPORT_PATH):
    st.error(
        f"No se encontró `{REPORT_PATH}`. "
        "Corré primero `python clickup_tasks.py` para generar el reporte."
    )
    st.stop()

df = load_data(REPORT_PATH, os.path.getmtime(REPORT_PATH))

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
st.sidebar.header("Filtros")

ALL_OPTION = "✓ Ver todos"


def multi_filter(label: str, options: list[str], key: str) -> list[str]:
    options = list(options)
    selected = st.sidebar.multiselect(
        label,
        options=[ALL_OPTION] + options,
        default=[ALL_OPTION],
        key=key,
    )
    if ALL_OPTION in selected or not selected:
        return options
    return selected


folders = sorted(df["folder_name"].dropna().unique().tolist())
sel_folders = multi_filter("Folder", folders, key="f_folder")

lists_available = sorted(
    df[df["folder_name"].isin(sel_folders)]["list_name"].dropna().unique().tolist()
)
sel_lists = multi_filter("Lista", lists_available, key="f_list")

statuses = sorted(df["status"].dropna().unique().tolist())
sel_statuses = multi_filter("Status", statuses, key="f_status")

all_assignees = sorted(
    {a.strip() for cell in df["assignees"].dropna() for a in str(cell).split(",") if a.strip()}
)
sel_assignees = multi_filter("Asignados", all_assignees, key="f_assignees")

min_d = df["date_created"].min()
max_d = df["date_created"].max()
if pd.notna(min_d) and pd.notna(max_d):
    col_from, col_to = st.sidebar.columns(2)
    date_from = col_from.date_input(
        "Desde",
        value=min_d.date(),
        min_value=min_d.date(),
        max_value=max_d.date(),
        format="DD/MM/YYYY",
    )
    date_to = col_to.date_input(
        "Hasta",
        value=max_d.date(),
        min_value=min_d.date(),
        max_value=max_d.date(),
        format="DD/MM/YYYY",
    )
    date_range = (date_from, date_to)
else:
    date_range = None

only_with_hours = st.sidebar.toggle("Solo tareas con horas > 0", value=False)

# ── APPLY FILTERS ─────────────────────────────────────────────────────────────
mask = (
    df["folder_name"].isin(sel_folders)
    & df["list_name"].isin(sel_lists)
    & df["status"].isin(sel_statuses)
)

if date_range and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    mask &= (df["date_created"] >= pd.Timestamp(start)) & (
        df["date_created"] <= pd.Timestamp(end) + pd.Timedelta(days=1)
    )

if only_with_hours:
    mask &= df["time_tracked_hours"] > 0

filtered = df[mask].copy()

if sel_assignees:
    filtered = filtered[
        filtered["assignees"].apply(
            lambda cell: any(a.strip() in sel_assignees for a in str(cell).split(","))
        )
    ]

# ── HEADER ────────────────────────────────────────────────────────────────────
st.title("📊 ClickUp Dashboard")
st.caption(
    f"Última actualización del reporte: "
    f"{datetime.fromtimestamp(os.path.getmtime(REPORT_PATH)).strftime('%Y-%m-%d %H:%M')}"
)

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_tasks = len(filtered)
closed_tasks = int((filtered["date_closed"].notna()).sum()) if "date_closed" in filtered else 0
open_tasks = total_tasks - closed_tasks
total_hours = float(filtered["time_tracked_hours"].sum())
avg_hours = total_hours / total_tasks if total_tasks else 0.0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tareas (filtradas)", f"{total_tasks:,}")
c2.metric("Abiertas", f"{open_tasks:,}")
c3.metric("Cerradas", f"{closed_tasks:,}")
c4.metric("Horas trackeadas", f"{total_hours:,.1f}")
c5.metric("Promedio h/tarea", f"{avg_hours:,.2f}")

st.divider()

# ── TABS ──────────────────────────────────────────────────────────────────────
tab_overview, tab_people, tab_status, tab_struct, tab_list, tab_table = st.tabs(
    [
        "🏠 Resumen",
        "👥 Por persona",
        "📌 Por status",
        "🗂️ Por folder/lista",
        "📁 Por lista",
        "📋 Detalle",
    ]
)

with tab_overview:
    if filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        today = pd.Timestamp(datetime.now().date())
        ov = filtered.copy()
        ov["is_closed"] = ov["date_closed"].notna()
        end_ref = ov["date_closed"].fillna(today)
        ov["dias_abierta"] = (end_ref - ov["date_created"]).dt.days
        ov["unassigned"] = ov["assignees"].fillna("Sin asignar").eq("Sin asignar")

        last_30 = today - pd.Timedelta(days=30)
        created_30 = int((ov["date_created"] >= last_30).sum())
        closed_30 = int((ov["date_closed"] >= last_30).sum())
        total = len(ov)
        closed = int(ov["is_closed"].sum())
        open_n = total - closed
        close_rate = (closed / total * 100) if total else 0
        unassigned_n = int(ov["unassigned"].sum())
        total_h = float(ov["time_tracked_hours"].sum())
        avg_h = total_h / total if total else 0

        st.subheader("KPIs")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total tareas", f"{total:,}")
        k2.metric("Abiertas", f"{open_n:,}")
        k3.metric("Cerradas", f"{closed:,}", f"{close_rate:.1f}% cierre")
        k4.metric("Sin asignar", f"{unassigned_n:,}")

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Horas totales", f"{total_h:,.1f}")
        k6.metric("Prom. h/tarea", f"{avg_h:,.2f}")
        k7.metric("Creadas (30d)", f"{created_30:,}")
        k8.metric("Cerradas (30d)", f"{closed_30:,}")

        st.divider()
        st.subheader("Highlights")

        exploded_ov = explode_assignees(ov)
        per_person_ov = (
            exploded_ov.groupby("assignee")["time_tracked_hours"]
            .sum()
            .sort_values(ascending=False)
        )
        top_person = per_person_ov.index[0] if len(per_person_ov) else "—"
        top_person_h = per_person_ov.iloc[0] if len(per_person_ov) else 0

        open_by_list = (
            ov[~ov["is_closed"]].groupby("list_name").size().sort_values(ascending=False)
        )
        top_open_list = open_by_list.index[0] if len(open_by_list) else "—"
        top_open_list_n = int(open_by_list.iloc[0]) if len(open_by_list) else 0

        open_tasks = ov[~ov["is_closed"]].copy()
        if not open_tasks.empty:
            oldest = open_tasks.sort_values("dias_abierta", ascending=False).iloc[0]
            oldest_name = str(oldest["task_name"])[:60]
            oldest_days = int(oldest["dias_abierta"])
            oldest_assignee = oldest["assignees"]
        else:
            oldest_name, oldest_days, oldest_assignee = "—", 0, "—"

        closed_tasks = ov[ov["is_closed"]].copy()
        if not closed_tasks.empty:
            avg_resolution = (
                closed_tasks.groupby("list_name")["dias_abierta"]
                .mean()
                .sort_values()
            )
            best_list = avg_resolution.index[0]
            best_list_days = avg_resolution.iloc[0]
        else:
            best_list, best_list_days = "—", 0

        stale_90 = int((open_tasks["dias_abierta"] > 90).sum())

        h1, h2, h3 = st.columns(3)
        with h1:
            st.markdown(f"**🏆 Persona con más horas**")
            st.markdown(f"### {top_person}")
            st.caption(f"{top_person_h:,.1f} horas trackeadas")
        with h2:
            st.markdown(f"**📦 Lista con más tareas abiertas**")
            st.markdown(f"### {top_open_list}")
            st.caption(f"{top_open_list_n} tareas abiertas")
        with h3:
            st.markdown(f"**⚡ Lista que cierra más rápido**")
            st.markdown(f"### {best_list}")
            st.caption(f"{best_list_days:.1f} días promedio")

        h4, h5 = st.columns(2)
        with h4:
            st.markdown(f"**🐌 Tarea más vieja sin cerrar**")
            st.markdown(f"### {oldest_days} días")
            st.caption(f"{oldest_name} — {oldest_assignee}")
        with h5:
            st.markdown(f"**⚠️ Tareas abiertas +90 días**")
            st.markdown(f"### {stale_90}")
            st.caption("revisar para desbloquear o cerrar")

        st.divider()
        st.subheader("Gráficos")

        g1, g2 = st.columns(2)
        with g1:
            monthly = pd.DataFrame(
                {
                    "Creadas": ov.groupby(ov["date_created"].dt.to_period("M")).size(),
                    "Cerradas": ov[ov["is_closed"]]
                    .groupby(ov[ov["is_closed"]]["date_closed"].dt.to_period("M"))
                    .size(),
                }
            ).fillna(0).astype(int)
            monthly.index = monthly.index.astype(str)
            monthly = monthly.reset_index().rename(columns={"index": "mes"})
            monthly_long = monthly.melt(id_vars="mes", var_name="tipo", value_name="tareas")
            fig = px.line(
                monthly_long,
                x="mes",
                y="tareas",
                color="tipo",
                markers=True,
                title="Tareas creadas vs cerradas por mes",
            )
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)
        with g2:
            bins = [-1, 7, 30, 90, float("inf")]
            labels_ag = ["0-7 días", "7-30 días", "30-90 días", "+90 días"]
            if not open_tasks.empty:
                open_tasks["bucket"] = pd.cut(
                    open_tasks["dias_abierta"], bins=bins, labels=labels_ag
                )
                aging = (
                    open_tasks.groupby("bucket", observed=True)
                    .size()
                    .reindex(labels_ag, fill_value=0)
                    .reset_index(name="tareas")
                )
                fig = px.bar(
                    aging,
                    x="bucket",
                    y="tareas",
                    text="tareas",
                    title="Aging de tareas abiertas",
                    color="bucket",
                    color_discrete_sequence=["#22c55e", "#eab308", "#f97316", "#ef4444"],
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(height=380, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay tareas abiertas.")

        g3, g4 = st.columns(2)
        with g3:
            top10 = per_person_ov.head(10).reset_index()
            top10.columns = ["assignee", "horas"]
            top10["horas"] = top10["horas"].round(1)
            fig = px.bar(
                top10,
                x="horas",
                y="assignee",
                text="horas",
                orientation="h",
                title="Top 10 personas por horas",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=380,
                yaxis={"categoryorder": "total ascending"},
            )
            st.plotly_chart(fig, use_container_width=True)
        with g4:
            by_status_ov = ov.groupby("status").size().reset_index(name="tareas")
            fig = px.pie(
                by_status_ov,
                names="status",
                values="tareas",
                title="Distribución por status",
                hole=0.5,
            )
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)



with tab_people:
    if filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        exploded = explode_assignees(filtered)
        per_person = (
            exploded.groupby("assignee")
            .agg(
                tareas=("task_id", "count"),
                horas=("time_tracked_hours", "sum"),
            )
            .reset_index()
            .sort_values("horas", ascending=False)
        )
        per_person["horas"] = per_person["horas"].round(2)
        per_person["prom_h_tarea"] = (
            (per_person["horas"] / per_person["tareas"]).round(2).fillna(0)
        )

        col_a, col_b = st.columns([2, 1])
        with col_a:
            fig = px.bar(
                per_person,
                x="assignee",
                y="horas",
                text="horas",
                title="Horas trackeadas por persona",
                labels={"assignee": "Asignado", "horas": "Horas"},
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(xaxis_tickangle=-30, height=420)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.dataframe(per_person, use_container_width=True, hide_index=True)

        fig2 = px.bar(
            per_person.sort_values("tareas", ascending=False),
            x="assignee",
            y="tareas",
            text="tareas",
            title="Cantidad de tareas por persona",
            labels={"assignee": "Asignado", "tareas": "Tareas"},
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(xaxis_tickangle=-30, height=380)
        st.plotly_chart(fig2, use_container_width=True)

with tab_status:
    if filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        by_status = (
            filtered.groupby("status")
            .agg(tareas=("task_id", "count"), horas=("time_tracked_hours", "sum"))
            .reset_index()
            .sort_values("tareas", ascending=False)
        )
        col_a, col_b = st.columns(2)
        with col_a:
            fig = px.pie(by_status, names="status", values="tareas", title="Tareas por status", hole=0.45)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            fig = px.bar(
                by_status,
                x="status",
                y="horas",
                text=by_status["horas"].round(1),
                title="Horas por status",
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

with tab_struct:
    if filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        by_folder = (
            filtered.groupby("folder_name")
            .agg(tareas=("task_id", "count"), horas=("time_tracked_hours", "sum"))
            .reset_index()
            .sort_values("horas", ascending=False)
        )
        fig = px.bar(
            by_folder,
            x="folder_name",
            y="horas",
            text=by_folder["horas"].round(1),
            title="Horas por folder",
        )
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

        by_list = (
            filtered.groupby(["folder_name", "list_name"])
            .agg(tareas=("task_id", "count"), horas=("time_tracked_hours", "sum"))
            .reset_index()
            .sort_values("horas", ascending=False)
        )
        st.dataframe(by_list, use_container_width=True, hide_index=True)

with tab_list:
    if filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        today = pd.Timestamp(datetime.now().date())
        work = filtered.copy()
        work["is_closed"] = work["date_closed"].notna()
        end_ref = work["date_closed"].fillna(today)
        work["dias_abierta"] = (end_ref - work["date_created"]).dt.days

        list_keys = ["folder_name", "list_name"]

        summary = (
            work.groupby(list_keys)
            .agg(
                tareas=("task_id", "count"),
                abiertas=("is_closed", lambda s: int((~s).sum())),
                cerradas=("is_closed", "sum"),
                dias_prom=("dias_abierta", "mean"),
                dias_max=("dias_abierta", "max"),
                horas=("time_tracked_hours", "sum"),
            )
            .reset_index()
            .sort_values("tareas", ascending=False)
        )
        summary["dias_prom"] = summary["dias_prom"].round(1)
        summary["horas"] = summary["horas"].round(2)
        summary["prom_h_tarea"] = (
            (summary["horas"] / summary["tareas"]).round(2).fillna(0)
        )

        list_options = summary["list_name"].tolist()
        sel_list = st.selectbox(
            "Mirar una lista en detalle (opcional)",
            options=["— Todas —"] + list_options,
        )

        st.subheader("Resumen por lista")
        st.dataframe(
            summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "folder_name": "Folder",
                "list_name": "Lista",
                "tareas": "Tareas",
                "abiertas": "Abiertas",
                "cerradas": "Cerradas",
                "dias_prom": "Días prom. abierta",
                "dias_max": "Días máx. abierta",
                "horas": "Horas",
                "prom_h_tarea": "Prom h/tarea",
            },
        )

        col_a, col_b = st.columns(2)
        with col_a:
            fig = px.bar(
                summary.head(20),
                x="list_name",
                y="tareas",
                text="tareas",
                title="Tareas por lista (top 20)",
                labels={"list_name": "Lista", "tareas": "Tareas"},
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(xaxis_tickangle=-30, height=420)
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            fig = px.bar(
                summary.sort_values("dias_prom", ascending=False).head(20),
                x="list_name",
                y="dias_prom",
                text="dias_prom",
                title="Días promedio abiertas (top 20)",
                labels={"list_name": "Lista", "dias_prom": "Días"},
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(xaxis_tickangle=-30, height=420)
            st.plotly_chart(fig, use_container_width=True)

        status_by_list = (
            work.groupby(["list_name", "status"])
            .size()
            .reset_index(name="tareas")
        )
        top_lists = summary.head(15)["list_name"].tolist()
        fig = px.bar(
            status_by_list[status_by_list["list_name"].isin(top_lists)],
            x="list_name",
            y="tareas",
            color="status",
            title="Distribución de status por lista (top 15)",
            labels={"list_name": "Lista", "tareas": "Tareas"},
        )
        fig.update_layout(xaxis_tickangle=-30, height=460, barmode="stack")
        st.plotly_chart(fig, use_container_width=True)

        if sel_list != "— Todas —":
            st.divider()
            st.subheader(f"Detalle: {sel_list}")
            list_df = work[work["list_name"] == sel_list].copy()

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Tareas", len(list_df))
            k2.metric("Abiertas", int((~list_df["is_closed"]).sum()))
            k3.metric("Cerradas", int(list_df["is_closed"].sum()))
            k4.metric("Días prom. abiertas", f"{list_df['dias_abierta'].mean():.1f}")
            k5.metric("Horas", f"{list_df['time_tracked_hours'].sum():.1f}")

            status_counts = (
                list_df.groupby("status").size().reset_index(name="tareas")
            )
            col_x, col_y = st.columns(2)
            with col_x:
                fig = px.pie(
                    status_counts,
                    names="status",
                    values="tareas",
                    title="Status",
                    hole=0.45,
                )
                st.plotly_chart(fig, use_container_width=True)
            with col_y:
                st.dataframe(
                    list_df[
                        [
                            "task_name",
                            "status",
                            "assignees",
                            "date_created",
                            "date_closed",
                            "dias_abierta",
                            "time_tracked_hours",
                        ]
                    ].sort_values("dias_abierta", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )

with tab_table:
    st.dataframe(
        filtered.sort_values("date_created", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Descargar CSV (filtrado)",
        data=csv,
        file_name="clickup_filtered.csv",
        mime="text/csv",
    )
