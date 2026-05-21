# src/db/models/__init__.py

from src.db.models.base import Base  # Important to import Base first
from src.db.models.user_identity import UserIdentity
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.webhook_events import WebhookEvent
from src.db.models.conversations import Conversation, ConversationMessage
from src.db.models.auth_audit_log import AuthAuditLog  # Audit logging
from src.db.models.product_analytics_event import ProductAnalyticsEvent
from src.db.models.strava_sync_status import StravaSyncStatus
from src.db.models.strava_ingestion_retry import StravaIngestionRetry
from src.db.models.user_hr_zones import UserHrZones
from src.db.models.coach_tools import CoachTool
from src.db.models.user_coach_preferences import UserCoachPreferences
from src.db.models.weekly_training_insights import WeeklyTrainingInsight
from src.db.models.memory.coach_interactions import CoachInteraction
from src.db.models.memory.session_summaries import SessionSummary
from src.db.models.memory.user_open_threads import UserOpenThread
from src.db.models.memory.user_plan_memories import UserPlanMemory
from src.db.models.memory.user_state_observations import UserStateObservation

# Add other models in the proper order if needed (e.g. tokens, activities)
