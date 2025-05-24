# src/db/dao/task_dao.py

from typing import Optional, List, Union
from psycopg2.extensions import connection as PGConn
from sqlite3 import Connection as SQLiteConn

DBConn = Union[PGConn, SQLiteConn]

def create_task(conn: DBConn, user_id: int, title: str, status: str = "pending") -> int:
    cur = conn.cursor()
    if isinstance(conn, SQLiteConn):
        cur.execute(
            "INSERT INTO tasks (user_id, title, status) VALUES (?, ?, ?)",
            (user_id, title, status),
        )
        task_id = cur.lastrowid
    else:
        cur.execute(
            "INSERT INTO tasks (user_id, title, status) VALUES (%s, %s, %s) RETURNING id",
            (user_id, title, status),
        )
        task_id = cur.fetchone()[0]
    conn.commit()
    return task_id

def get_task(conn: DBConn, task_id: int) -> Optional[dict]:
    cur = conn.cursor()
    if isinstance(conn, SQLiteConn):
        cur.execute("SELECT id, user_id, title, status FROM tasks WHERE id = ?", (task_id,))
    else:
        cur.execute("SELECT id, user_id, title, status FROM tasks WHERE id = %s", (task_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "title": row[2],
        "status": row[3],
    }

def get_tasks(conn: DBConn) -> List[dict]:
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, title, status FROM tasks")
    rows = cur.fetchall()
    return [
        {"id": row[0], "user_id": row[1], "title": row[2], "status": row[3]}
        for row in rows
    ]

def update_task_status(conn: DBConn, task_id: int, status: str) -> None:
    cur = conn.cursor()
    if isinstance(conn, SQLiteConn):
        cur.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    else:
        cur.execute("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id))
    conn.commit()

def delete_task(conn: DBConn, task_id: int) -> None:
    cur = conn.cursor()
    if isinstance(conn, SQLiteConn):
        cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    else:
        cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
