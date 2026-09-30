import sqlite3
from datetime import date
from itertools import groupby
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
YEAR = 2026
DB_FILE = BASE_DIR / "data" / f"f1_data_{YEAR}.db"

app = FastAPI(title="F1 Pitstop")
app.mount("/images", StaticFiles(directory=BASE_DIR / "images"), name="images")
app.mount("/static", StaticFiles(directory=BASE_DIR / "src" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "src" / "templates")


def get_sessions():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM calendar ORDER BY start_date, start_time"
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def get_rounds(sessions):
    # Sessions are date-ordered, so consecutive sessions at one location form a race weekend
    rounds = []
    for (country, location), weekend in groupby(sessions, key=lambda s: (s["country"], s["location"])):
        weekend = list(weekend)
        rounds.append({
            "number": len(rounds) + 1,
            "country": country,
            "location": location,
            "start_date": weekend[0]["start_date"],
            "end_date": weekend[-1]["start_date"],
            "sessions": weekend,
        })
    return rounds


@app.get("/")
def index():
    return RedirectResponse(url="/calendar")


@app.get("/calendar")
def calendar(request: Request):
    rounds = get_rounds(get_sessions())
    today = date.today().isoformat()
    next_round = next((r["number"] for r in rounds if r["end_date"] >= today), None)
    return templates.TemplateResponse(
        request,
        "calendar.html",
        {"year": YEAR, "rounds": rounds, "today": today, "next_round": next_round, "active_tab": "calendar"},
    )


@app.get("/api/calendar")
def calendar_api():
    return get_sessions()
