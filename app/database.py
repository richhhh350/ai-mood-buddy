from pathlib import Path
from contextlib import contextmanager
import sqlite3


DB_PATH = Path(__file__).parent.parent / "data" / "mood_buddy.db"


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_database():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS mood_entries (
                id TEXT PRIMARY KEY,
                original_text TEXT NOT NULL,
                mood TEXT NOT NULL,
                emoji TEXT NOT NULL,
                intensity INTEGER NOT NULL CHECK (intensity BETWEEN 1 AND 5),
                response TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def create_entry(entry):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO mood_entries (
                id, original_text, mood, emoji, intensity,
                response, action, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["id"],
                entry["original_text"],
                entry["mood"],
                entry["emoji"],
                entry["intensity"],
                entry["response"],
                entry["action"],
                entry["created_at"],
            ),
        )
    return entry


def list_entries(limit=20):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, original_text, mood, emoji, intensity,
                   response, action, created_at
            FROM mood_entries
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_entry(entry_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM mood_entries WHERE id = ?",
            (entry_id,),
        )
    return cursor.rowcount > 0


def clear_entries():
    with get_connection() as connection:
        connection.execute("DELETE FROM mood_entries")
