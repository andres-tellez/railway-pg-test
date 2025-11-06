# src/db/models/__init__.py

from src.db.models.base import Base  # Important to import Base first
from src.db.models.user_identity import UserIdentity
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.webhook_events import WebhookEvent
from src.db.models.conversations import Conversation, ConversationMessage
from src.db.models.auth_audit_log import AuthAuditLog  # Audit logging

# Add other models in the proper order if needed (e.g. tokens, activities)
