# src/utils/gpt_ops.py

import os
from flask import Flask
from src.db.base_model import get_session
from src.db.dao.task_dao import create_task, update_task_status, delete_task

# Optional: load app context if needed

def init_flask_context():
    from src.app import create_app
    app = create_app({"TESTING": True})
    ctx = app.app_context()
    ctx.push()

# Check if GPT is allowed to modify DB
if os.getenv("GPT_CAN_MUTATE_DB", "false").lower() == "true":
    init_flask_context()
else:
    raise RuntimeError("GPT task creation is disabled by config. Set GPT_CAN_MUTATE_DB=true in your .env.")


def create_task_from_gpt(title, user_id=1, status="pending", milestone=None, labels=None, is_icebox=False, details=None):
    session = get_session()
    try:
        task_id = create_task(
            session,
            user_id=user_id,
            title=title,
            status=status,
            milestone=milestone,
            labels=labels,
            is_icebox=is_icebox,
            details=details,
        )
        print(f"✅ GPT created task #{task_id}: {title}")
        return task_id
    except Exception as e:
        print(f"❌ GPT failed to create task: {e}")
    finally:
        session.close()


def update_task_status_from_gpt(task_id, status=None, labels=None, is_icebox=None, details=None):
    session = get_session()
    try:
        update_task_status(
            session,
            task_id=task_id,
            status=status,
            labels=labels,
            is_icebox=is_icebox,
            details=details,
        )
        print(f"✅ GPT updated task #{task_id}")
    except Exception as e:
        print(f"❌ GPT failed to update task #{task_id}: {e}")
    finally:
        session.close()


def delete_task_by_id_from_gpt(task_id):
    session = get_session()
    try:
        delete_task(session, task_id)
        print(f"🗑️ GPT deleted task #{task_id}")
    except Exception as e:
        print(f"❌ GPT failed to delete task #{task_id}: {e}")
    finally:
        session.close()
