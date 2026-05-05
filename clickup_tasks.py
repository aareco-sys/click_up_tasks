import os
import requests
import pandas as pd
from datetime import datetime

TOKEN = os.getenv("CLICKUP_TOKEN")

if not TOKEN:
    raise ValueError("Falta la variable de entorno CLICKUP_TOKEN")

SPACE_ID = "90020465072"

headers = {"Authorization": TOKEN}


def format_date(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d")


def ms_to_hours(ms):
    return round(int(ms) / 3_600_000, 2)


def get_time_tracked(task_id: str) -> float:
    """
    Llama a /task/{task_id}/time y suma el tiempo de todos los usuarios.
    Retorna horas totales (float).
    """
    res = requests.get(
        f"https://api.clickup.com/api/v2/task/{task_id}/time",
        headers=headers
    ).json()

    total_ms = sum(int(entry.get("time", 0)) for entry in res.get("data", []))
    return ms_to_hours(total_ms)


# ── 1. TAREAS ─────────────────────────────────────────────────────────────────

all_tasks = []

folders_url = f"https://api.clickup.com/api/v2/space/{SPACE_ID}/folder"
folders_res = requests.get(folders_url, headers=headers).json()

for folder in folders_res.get("folders", []):
    folder_name = folder["name"]

    for lst in folder.get("lists", []):
        list_id   = lst["id"]
        list_name = lst["name"]
        print(f"\nProcesando list: {list_name}")

        page = 0
        while True:
            tasks_url = (
                f"https://api.clickup.com/api/v2/list/{list_id}/task"
                f"?include_closed=true&page={page}"
            )
            tasks_res = requests.get(tasks_url, headers=headers).json()
            tasks = tasks_res.get("tasks", [])
            if not tasks:
                break

            for task in tasks:
                task_id = task.get("id")
                print(f"    → Trayendo tiempo: {task_id} - {task.get('name')[:40]}")

                assignees = task.get("assignees", []) or []
                assignee_names = ", ".join(a.get("username", "") for a in assignees) or "Sin asignar"
                assignee_emails = ", ".join(a.get("email", "") for a in assignees)

                all_tasks.append({
                    "folder_name":        folder_name,
                    "list_name":          list_name,
                    "task_name":          task.get("name"),
                    "status":             task.get("status", {}).get("status"),
                    "assignees":          assignee_names,
                    "assignee_emails":    assignee_emails,
                    "date_created":       format_date(task.get("date_created")),
                    "date_closed":        format_date(task.get("date_closed")),
                    "time_tracked_hours": get_time_tracked(task_id),  # ← fetch individual
                    "task_id":            task_id,
                })

            print(f"  Página {page}: {len(tasks)} tasks")
            page += 1

print(f"\nTotal tasks: {len(all_tasks)}")


# ── 2. EXCEL ──────────────────────────────────────────────────────────────────

df = pd.DataFrame(all_tasks)
df.to_excel("clickup_tasks_report.xlsx", index=False)

print("\n✅ Excel generado: clickup_tasks_report.xlsx")
print(df[df["time_tracked_hours"] > 0].to_string(index=False))