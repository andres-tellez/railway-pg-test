# src/db/dao/task_dao.py

from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def create_task(session: Session, user_id: int, title: str, status: str = "pending",
                milestone: Optional[str] = None, labels: Optional[List[str]] = None,
                is_icebox: bool = False, details: Optional[str] = None) -> int:
    labels_str = ",".join(labels) if labels else None

    # Workaround for SQLite (no RETURNING id)
    if session.bind.dialect.name == "sqlite":
        session.execute(text("""
            INSERT INTO tasks (user_id, title, status, milestone, labels, is_icebox, details)
            VALUES (:user_id, :title, :status, :milestone, :labels, :is_icebox, :details)
        """), {
            "user_id": user_id,
            "title": title,
            "status": status,
            "milestone": milestone,
            "labels": labels_str,
            "is_icebox": is_icebox,
            "details": details
        })
        task_id = session.execute(text("SELECT last_insert_rowid()")).scalar()
    else:
        result = session.execute(text("""
            INSERT INTO tasks (user_id, title, status, milestone, labels, is_icebox, details)
            VALUES (:user_id, :title, :status, :milestone, :labels, :is_icebox, :details)
            RETURNING id
        """), {
            "user_id": user_id,
            "title": title,
            "status": status,
            "milestone": milestone,
            "labels": labels_str,
            "is_icebox": is_icebox,
            "details": details
        })
        task_id = result.scalar()

    session.commit()
    return task_id


def get_task(session: Session, task_id: int) -> Optional[dict]:
    result = session.execute(text("""
        SELECT id, user_id, title, status, milestone, labels, is_icebox, details
        FROM tasks
        WHERE id = :task_id
    """), {"task_id": task_id}).fetchone()

    if not result:
        return None

    return {
        "id": result.id,
        "user_id": result.user_id,
        "title": result.title,
        "status": result.status,
        "milestone": result.milestone,
        "labels": result.labels.split(",") if result.labels else [],
        "is_icebox": bool(result.is_icebox),
        "details": result.details,
    }


def get_tasks(session: Session, status: Optional[str] = None, milestone: Optional[str] = None,
              label: Optional[str] = None, is_icebox: Optional[bool] = None) -> List[dict]:
    base_query = """
        SELECT id, user_id, title, status, milestone, labels, is_icebox, details
        FROM tasks
    """
    conditions = []
    params = {}

    if status:
        conditions.append("status = :status")
        params["status"] = status
    if milestone:
        conditions.append("milestone = :milestone")
        params["milestone"] = milestone
    if label:
        conditions.append("labels LIKE :label")
        params["label"] = f"%{label}%"
    if is_icebox is not None:
        conditions.append("is_icebox = :is_icebox")
        params["is_icebox"] = is_icebox

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    result = session.execute(text(base_query), params).fetchall()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "title": row.title,
            "status": row.status,
            "milestone": row.milestone,
            "labels": row.labels.split(",") if row.labels else [],
            "is_icebox": bool(row.is_icebox),
            "details": row.details,
        }
        for row in result
    ]


def update_task_status(session: Session, task_id: int, status: Optional[str] = None,
                       labels: Optional[List[str]] = None, is_icebox: Optional[bool] = None,
                       details: Optional[str] = None) -> None:
    updates = []
    params = {"task_id": task_id}

    if status is not None:
        updates.append("status = :status")
        params["status"] = status
    if labels is not None:
        updates.append("labels = :labels")
        params["labels"] = ",".join(labels)
    if is_icebox is not None:
        updates.append("is_icebox = :is_icebox")
        params["is_icebox"] = is_icebox
    if details is not None:
        updates.append("details = :details")
        params["details"] = details

    if not updates:
        return

    query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = :task_id"
    session.execute(text(query), params)
    session.commit()


def delete_task(session: Session, task_id: int) -> None:
    session.execute(text("DELETE FROM tasks WHERE id = :task_id"), {"task_id": task_id})
    session.commit()
