import sqlite3
from fetch_f1_data import *

DB_FILE = "data/f1_data.db"

SCHEMA = """
DROP TABLE IF EXISTS session_ids;
CREATE TABLE session_ids(
                            id     INTEGER     PRIMARY KEY AUTOINCREMENT,
                            track  TEXT        NOT NULL
);
"""

def create_tables(conn):
    conn.executescript(SCHEMA)

def update_database(conn):
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO session_ids (id, track) VALUES (?, ?)",
        [
            ("1111", "BAHRAIN"),
        ],
    )
    conn.commit()
 
def main():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        create_tables(conn)
        update_database(conn)
    finally:
        conn.close()

main()