"""Factory for building MemoryService with concrete adapters."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.memory.adapters.classifier_openai import (
    OpenAIClassifierClient,
)
from src.smartcoach_mobile_coach.memory.adapters.durable_pg import DurableRepoPG
from src.smartcoach_mobile_coach.memory.adapters.interaction_pg import InteractionRepoPG
from src.smartcoach_mobile_coach.memory.adapters.state_pg import StateRepoPG
from src.smartcoach_mobile_coach.memory.adapters.summarizer_llm import (
    SummarizerLLMAdapter,
)
from src.smartcoach_mobile_coach.memory.adapters.summary_pg import SummaryRepoPG
from src.smartcoach_mobile_coach.memory.adapters.threads_pg import ThreadRepoPG
from src.smartcoach_mobile_coach.memory.config import MemoryConfig
from src.smartcoach_mobile_coach.memory.defaults import (
    BasicPromptRenderer,
    NoopCallbackPolicy,
)
from src.smartcoach_mobile_coach.memory.policies.classifier import (
    LLMObservationClassifier,
)
from src.smartcoach_mobile_coach.memory.service import MemoryService


def build_memory_service(session: Session, cfg: MemoryConfig) -> MemoryService:
    """Construct MemoryService with project-default adapters and policies."""
    classifier = LLMObservationClassifier(
        llm_client=OpenAIClassifierClient(),
        timeout_s=cfg.classifier_timeout_s,
        llm_enabled=cfg.classifier_enabled,
    )
    return MemoryService(
        durable_repo=DurableRepoPG(session),
        state_repo=StateRepoPG(session),
        thread_repo=ThreadRepoPG(session),
        interaction_repo=InteractionRepoPG(session),
        summary_repo=SummaryRepoPG(session),
        summarizer_llm=SummarizerLLMAdapter(),
        classifier=classifier,
        callback_policy=NoopCallbackPolicy(),
        prompt_renderer=BasicPromptRenderer(),
    )
