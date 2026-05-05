import os
import time
from datetime import datetime

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

API_KEY = os.getenv("FRESHDESK_API_KEY")
DOMAIN = os.getenv("FRESHDESK_DOMAIN", "dinocloud-us")

if not API_KEY:
    raise ValueError("Falta la variable de entorno FRESHDESK_API_KEY")

BASE = f"https://{DOMAIN}.freshdesk.com/api/v2"
AUTH = HTTPBasicAuth(API_KEY, "X")

STATUS_MAP = {
    2: "Open",
    3: "Pending",
    4: "Resolved",
    5: "Closed",
    6: "Waiting on Customer",
    7: "Waiting on Third Party",
}
PRIORITY_MAP = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
SOURCE_MAP = {
    1: "Email",
    2: "Portal",
    3: "Phone",
    5: "Chat",
    6: "Mobihelp",
    7: "Feedback Widget",
    8: "Outbound Email",
    9: "Ecommerce",
    10: "Bot",
}


def get_json(url: str, params: dict | None = None, max_retries: int = 5):
    for attempt in range(max_retries):
        r = requests.get(url, auth=AUTH, params=params, timeout=60)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 30))
            print(f"  ⏳ Rate limited. Esperando {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Excedido reintentos: {url}")


def paginate(path: str, params: dict | None = None, max_pages: int = 300):
    out = []
    page = 1
    base_params = {"per_page": 100, **(params or {})}
    while page <= max_pages:
        data = get_json(f"{BASE}/{path}", params={**base_params, "page": page})
        if not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
        page += 1
    return out


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.replace("Z", "")[:19], "%Y-%m-%dT%H:%M:%S").strftime(
            "%Y-%m-%d"
        )
    except Exception:
        return s


def time_to_hours(s: str | None) -> float:
    if not s:
        return 0.0
    try:
        h, m, *_ = s.split(":")
        return round(int(h) + int(m) / 60, 2)
    except Exception:
        return 0.0


print("→ Cargando agentes, grupos y compañías...")
agents_raw = paginate("agents")
agents = {
    a["id"]: {
        "name": (a.get("contact") or {}).get("name") or (a.get("contact") or {}).get("email"),
        "email": (a.get("contact") or {}).get("email"),
    }
    for a in agents_raw
}
groups = {g["id"]: g["name"] for g in paginate("groups")}
companies = {c["id"]: c["name"] for c in paginate("companies")}
print(f"  agentes={len(agents)} grupos={len(groups)} compañías={len(companies)}")

print("→ Cargando tickets (incluye stats y resueltos/cerrados)...")
raw_tickets = paginate(
    "tickets",
    params={"include": "stats", "updated_since": "2010-01-01T00:00:00Z"},
)
print(f"  Total tickets: {len(raw_tickets)}")

print("→ Cargando time entries (workspace)...")
raw_entries = paginate("time_entries")
print(f"  Total time entries: {len(raw_entries)}")

hours_by_ticket: dict[int, float] = {}
for e in raw_entries:
    tid = e.get("ticket_id")
    if tid is None:
        continue
    hours_by_ticket[tid] = hours_by_ticket.get(tid, 0.0) + time_to_hours(e.get("time_spent"))

tickets_rows = []
for t in raw_tickets:
    stats = t.get("stats") or {}
    rid = t.get("responder_id")
    gid = t.get("group_id")
    cid = t.get("company_id")
    tickets_rows.append(
        {
            "ticket_id": t.get("id"),
            "subject": t.get("subject"),
            "status": STATUS_MAP.get(t.get("status"), str(t.get("status"))),
            "priority": PRIORITY_MAP.get(t.get("priority"), str(t.get("priority"))),
            "source": SOURCE_MAP.get(t.get("source"), str(t.get("source"))),
            "type": t.get("type") or "Sin tipo",
            "agent": (agents.get(rid) or {}).get("name") or "Sin asignar",
            "agent_email": (agents.get(rid) or {}).get("email") or "",
            "group": groups.get(gid) or "Sin grupo",
            "company": companies.get(cid) or "",
            "requester_email": t.get("email") or "",
            "tags": ", ".join(t.get("tags") or []),
            "created_at": parse_date(t.get("created_at")),
            "updated_at": parse_date(t.get("updated_at")),
            "resolved_at": parse_date(stats.get("resolved_at")),
            "closed_at": parse_date(stats.get("closed_at")),
            "first_responded_at": parse_date(stats.get("first_responded_at")),
            "due_by": parse_date(t.get("due_by")),
            "fr_due_by": parse_date(t.get("fr_due_by")),
            "is_escalated": bool(t.get("is_escalated")),
            "spam": bool(t.get("spam")),
            "time_tracked_hours": round(hours_by_ticket.get(t.get("id"), 0.0), 2),
        }
    )

entries_rows = []
for e in raw_entries:
    aid = e.get("agent_id") or e.get("executed_by")
    entries_rows.append(
        {
            "entry_id": e.get("id"),
            "ticket_id": e.get("ticket_id"),
            "agent": (agents.get(aid) or {}).get("name") or "Sin asignar",
            "agent_email": (agents.get(aid) or {}).get("email") or "",
            "billable": e.get("billable"),
            "note": e.get("note"),
            "time_spent": e.get("time_spent"),
            "hours": time_to_hours(e.get("time_spent")),
            "executed_at": parse_date(e.get("executed_at")),
            "created_at": parse_date(e.get("created_at")),
            "updated_at": parse_date(e.get("updated_at")),
        }
    )

df_tickets = pd.DataFrame(tickets_rows)
df_entries = pd.DataFrame(entries_rows)

with pd.ExcelWriter("freshdesk_tickets_report.xlsx", engine="openpyxl") as w:
    df_tickets.to_excel(w, index=False, sheet_name="tickets")
    df_entries.to_excel(w, index=False, sheet_name="time_entries")

print("\n✅ Excel generado: freshdesk_tickets_report.xlsx")
print(f"   Tickets: {len(df_tickets)} | Time entries: {len(df_entries)}")
