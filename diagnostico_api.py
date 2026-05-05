import os
import requests
from datetime import datetime

TOKEN = os.getenv("CLICKUP_TOKEN")
if not TOKEN:
    raise ValueError("Falta la variable de entorno CLICKUP_TOKEN")

TEAM_ID = "90021032350"
TASK_ID = "86dzk3ztz"

headers = {"Authorization": TOKEN}

start_ms = int(datetime(2024, 1, 1).timestamp() * 1000)
end_ms   = int(datetime.now().timestamp() * 1000)

# ── Endpoint A: /task/{task_id}/time  ────────────────────────────────────────
print("=== ENDPOINT A: /task/{task_id}/time ===")
res_a = requests.get(
    f"https://api.clickup.com/api/v2/task/{TASK_ID}/time",
    headers=headers
)
print("Status:", res_a.status_code)
print(res_a.json())

# ── Endpoint B: /team/{team_id}/time_entries?task_id=  ───────────────────────
print("\n=== ENDPOINT B: /team/{team_id}/time_entries con task_id ===")
res_b = requests.get(
    f"https://api.clickup.com/api/v2/team/{TEAM_ID}/time_entries",
    headers=headers,
    params={"task_id": TASK_ID, "start_date": start_ms, "end_date": end_ms}
)
print("Status:", res_b.status_code)
print(res_b.json())

# ── Endpoint C: igual pero SIN filtro de fecha  ──────────────────────────────
print("\n=== ENDPOINT C: /team/{team_id}/time_entries SIN fechas ===")
res_c = requests.get(
    f"https://api.clickup.com/api/v2/team/{TEAM_ID}/time_entries",
    headers=headers,
    params={"task_id": TASK_ID}
)
print("Status:", res_c.status_code)
print(res_c.json())
