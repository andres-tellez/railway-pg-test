import os
import tempfile
import pytest
from sqlite3 import connect as sqlite_connect
from src.db.dao import task_dao

def setup_sqlite_schema(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id BIGINT NOT NULL,
        title TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        milestone TEXT,
        labels TEXT,
        is_icebox BOOLEAN DEFAULT FALSE
    )
    """)
    conn.commit()

def test_task_filters():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    db_path = tmp.name

    try:
        conn = sqlite_connect(db_path)
        setup_sqlite_schema(conn)

        task_dao.create_task(conn, 1, "A", status="done", milestone="MVP", labels=["backend"], is_icebox=False)
        task_dao.create_task(conn, 1, "B", status="pending", milestone="MVP", labels=["api"], is_icebox=False)
        task_dao.create_task(conn, 1, "C", status="in_progress", milestone="M2", labels=["frontend"], is_icebox=True)

        assert len(task_dao.get_tasks(conn, status="done")) == 1
        assert task_dao.get_tasks(conn, status="done")[0]["title"] == "A"

        assert len(task_dao.get_tasks(conn, milestone="MVP")) == 2
        assert len(task_dao.get_tasks(conn, status="pending", milestone="MVP")) == 1
        assert task_dao.get_tasks(conn, status="pending", milestone="MVP")[0]["title"] == "B"

        assert len(task_dao.get_tasks(conn, is_icebox=True)) == 1
        assert task_dao.get_tasks(conn, is_icebox=True)[0]["title"] == "C"

        assert task_dao.get_tasks(conn, status="archived") == []
    finally:
        conn.close()
        os.unlink(db_path)


def test_update_and_delete_task():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    db_path = tmp.name

    try:
        conn = sqlite_connect(db_path)
        setup_sqlite_schema(conn)

        task_id = task_dao.create_task(conn, 1, "Do something", status="pending")
        task_dao.update_task_status(conn, task_id, "done")
        task = task_dao.get_task(conn, task_id)
        assert task["status"] == "done"

        task_dao.delete_task(conn, task_id)
        assert task_dao.get_task(conn, task_id) is None
    finally:
        conn.close()  # 👈 Required before file deletion on Windows
        os.unlink(db_path)
