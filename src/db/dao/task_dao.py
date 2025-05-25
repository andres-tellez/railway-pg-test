# src/dao/task_dao.py

from typing import Optional, List, Union
from psycopg2.extensions import connection as PGConn
from sqlite3 import Connection as SQLiteConn

DBConn = Union[PGConn, SQLiteConn]

def create_task(conn: DBConn, user_id: int, title: str, status: str = "pending", milestone: Optional[str] = None, labels: Optional[List[str]] = None, is_icebox: bool = False) -> int:
    cur = conn.cursor()
    labels_str = ",".join(labels) if labels else None
    if isinstance(conn, SQLiteConn):
        cur.execute(
            """
            INSERT INTO tasks (user_id, title, status, milestone, labels, is_icebox)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, status, milestone, labels_str, is_icebox),
        )
        task_id = cur.lastrowid
    else:
        cur.execute(
            """
            INSERT INTO tasks (user_id, title, status, milestone, labels, is_icebox)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (user_id, title, status, milestone, labels_str, is_icebox),
        )
        task_id = cur.fetchone()[0]
    conn.commit()
    return task_id

def get_task(conn: DBConn, task_id: int) -> Optional[dict]:
    cur = conn.cursor()
    query = "SELECT id, user_id, title, status, milestone, labels, is_icebox FROM tasks WHERE id = ?" if isinstance(conn, SQLiteConn) else "SELECT id, user_id, title, status, milestone, labels, is_icebox FROM tasks WHERE id = %s"
    cur.execute(query, (task_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "title": row[2],
        "status": row[3],
        "milestone": row[4],
        "labels": row[5].split(",") if row[5] else [],
        "is_icebox": bool(row[6]),
    }

def get_tasks(conn: DBConn, status: Optional[str] = None, milestone: Optional[str] = None, label: Optional[str] = None, is_icebox: Optional[bool] = None) -> List[dict]:
    cur = conn.cursor()
    base_query = "SELECT id, user_id, title, status, milestone, labels, is_icebox FROM tasks"
    conditions = []
    params = []

    def clause(col): return f"{col} = ?" if isinstance(conn, SQLiteConn) else f"{col} = %s"

    if status:
        conditions.append(clause("status"))
        params.append(status)
    if milestone:
        conditions.append(clause("milestone"))
        params.append(milestone)
    if label:
        if isinstance(conn, SQLiteConn):
            conditions.append("labels LIKE ?")
            params.append(f"%{label}%")
        else:
            conditions.append("labels ILIKE %s")
            params.append(f"%{label}%")
    if is_icebox is not None:
        conditions.append(clause("is_icebox"))
        params.append(is_icebox)

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    cur.execute(base_query, tuple(params))
    rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "user_id": row[1],
            "title": row[2],
            "status": row[3],
            "milestone": row[4],
            "labels": row[5].split(",") if row[5] else [],
            "is_icebox": bool(row[6]),
        }
        for row in rows
    ]

def update_task_status(conn: DBConn, task_id: int, status: str) -> None:
    cur = conn.cursor()
    query = "UPDATE tasks SET status = ? WHERE id = ?" if isinstance(conn, SQLiteConn) else "UPDATE tasks SET status = %s WHERE id = %s"
    cur.execute(query, (status, task_id))
    conn.commit()

def delete_task(conn: DBConn, task_id: int) -> None:
    cur = conn.cursor()
    query = "DELETE FROM tasks WHERE id = ?" if isinstance(conn, SQLiteConn) else "DELETE FROM tasks WHERE id = %s"
    cur.execute(query, (task_id,))
    conn.commit()
