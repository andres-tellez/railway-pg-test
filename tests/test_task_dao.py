import pytest
from src.db.dao import task_dao
from sqlalchemy import text

@pytest.fixture(scope="function", autouse=True)
def setup_tasks_schema(sqlalchemy_engine):
    with sqlalchemy_engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            milestone TEXT,
            labels TEXT,
            is_icebox BOOLEAN DEFAULT FALSE,
            details TEXT
        )
        """))

def test_task_filters(sqlalchemy_session):
    task_dao.create_task(sqlalchemy_session, 1, "A", status="done", milestone="MVP", labels=["backend"], is_icebox=False)
    task_dao.create_task(sqlalchemy_session, 1, "B", status="pending", milestone="MVP", labels=["api"], is_icebox=False)
    task_dao.create_task(sqlalchemy_session, 1, "C", status="in_progress", milestone="M2", labels=["frontend"], is_icebox=True)

    assert len(task_dao.get_tasks(sqlalchemy_session, status="done")) == 1
    assert task_dao.get_tasks(sqlalchemy_session, status="done")[0]["title"] == "A"

    assert len(task_dao.get_tasks(sqlalchemy_session, milestone="MVP")) == 2
    assert len(task_dao.get_tasks(sqlalchemy_session, status="pending", milestone="MVP")) == 1
    assert task_dao.get_tasks(sqlalchemy_session, status="pending", milestone="MVP")[0]["title"] == "B"

    assert len(task_dao.get_tasks(sqlalchemy_session, is_icebox=True)) == 1
    assert task_dao.get_tasks(sqlalchemy_session, is_icebox=True)[0]["title"] == "C"

    assert task_dao.get_tasks(sqlalchemy_session, status="archived") == []

def test_update_and_delete_task(sqlalchemy_session):
    task_id = task_dao.create_task(sqlalchemy_session, 1, "Do something", status="pending")
    task_dao.update_task_status(sqlalchemy_session, task_id, status="done")
    task = task_dao.get_task(sqlalchemy_session, task_id)
    assert task["status"] == "done"

    task_dao.delete_task(sqlalchemy_session, task_id)
    assert task_dao.get_task(sqlalchemy_session, task_id) is None
