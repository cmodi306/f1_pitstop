import sqlite3
from fetch_f1_data import *


SCHEMA = """
DROP TABLE IF EXISTS calendar;
CREATE TABLE IF NOT EXISTS calendar(
                            country       TEXT      NOT NULL,
                            location      TEXT,
                            session_key   INTEGER   PRIMARY KEY,
                            session_type  TEXT,
                            start_date    TEXT      NOT NULL,
                            start_time    TEXT      NOT NULL
);
"""

def create_tables(conn):
    conn.executescript(SCHEMA)

def update_database(conn, f1_cal):
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO calendar (country, location, session_key, session_type, start_date, start_time)
        VALUES (:country, :location, :session_key, :session_type, :start_date, :start_time)
        ON CONFLICT(session_key) DO UPDATE SET
            country      = excluded.country,
            location     = excluded.location,
            session_type = excluded.session_type,
            start_date   = excluded.start_date,
            start_time   = excluded.start_time
        """,
        f1_cal,
    )
    conn.commit()
 
def main(year):
    DB_FILE = f"data/f1_data_{year}.db"
    f1_cal = get_f1_calendar(2026)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        create_tables(conn)
        update_database(conn, f1_cal=f1_cal)
    finally:
        conn.close()

main(2026)