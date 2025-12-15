"""
Coach Orchestrator - Main entry point for Coach system.

Orchestrates all Coach components to process user questions.
"""

import logging
from typing import Dict, Any, Optional, List

from sqlalchemy.orm import Session

from coach.utils.intent_classifier import IntentClassifier
from coach.safety.safety_scanner import SafetyScanner
from coach.builders.runner_state_builder import RunnerStateBuilder
from coach.builders.question_context_builder import QuestionContextBuilder
from coach.prompts.prompt_builder import CoachPromptBuilder
from coach.llm.llm_client import LLMClient, LLMRequest
from coach.formatters.response_formatter import ResponseFormatter
from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity

logger = logging.getLogger(__name__)


class CoachOrchestrator:
    """
    Main orchestrator for the Coach system.

    Coordinates all components to process user questions:
    1. Classify intent
    2. Scan for safety flags
    3. Build RunnerState
    4. Build QuestionContext
    5. Build prompt
    6. Get LLM response
    7. Format response
    """

    def __init__(self, session: Session, user_id: str):
        """
        Initialize CoachOrchestrator.

        Args:
            session: Database session
            user_id: User ID
        """
        self.session = session
        self.user_id = user_id
        self.intent_classifier = IntentClassifier()
        self.safety_scanner = SafetyScanner()
        self.runner_state_builder = RunnerStateBuilder(session, user_id)
        self.question_context_builder = QuestionContextBuilder(session, user_id)
        self.prompt_builder = CoachPromptBuilder()
        self.llm_client = LLMClient()
        self.response_formatter = ResponseFormatter()

    def process_question(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user question through the full Coach pipeline.

        Args:
            question: User's question
            conversation_history: Optional conversation history

        Returns:
            Dict with:
            - response: Formatted response content
            - metadata: Processing metadata (intent, safety flags, etc.)
            - usage: LLM usage information
        """
        try:
            # 1. Classify intent
            intent_result = self.intent_classifier.classify(question)
            intent = intent_result.intent
            logger.info(
                f"Classified intent: {intent} (confidence: {intent_result.confidence})"
            )

            # 2. Scan for safety flags
            safety_scan = self.safety_scanner.scan_for_schema(question)
            safety_flags = safety_scan.get("safety_flags", {})
            logger.info(
                f"Safety scan: {len(safety_flags.get('flags', []))} flags detected"
            )

            # 3. Build RunnerState
            runner_state = self.runner_state_builder.build()
            logger.info(
                f"RunnerState built: phase={runner_state.get('runner_state', {}).get('phase', 'Unknown')}"
            )

            # 4. Build QuestionContext
            question_context = self.question_context_builder.build(question)
            logger.info(
                f"QuestionContext built: intent={question_context.get('question_context', {}).get('intent', 'Unknown')}"
            )

            # 5. Build prompt
            messages = self.prompt_builder.build(
                runner_state=runner_state,
                question_context=question_context,
                user_question=question,
                conversation_history=conversation_history,
            )
            logger.info(f"Prompt built: {len(messages)} messages")

            # 6. Get LLM response
            llm_request = LLMRequest(
                messages=messages,
                user_id=self.user_id,
            )
            llm_response = self.llm_client.chat_completion(llm_request)
            logger.info(
                f"LLM response received: {llm_response.usage.get('total_tokens', 0)} tokens"
            )

            # 7. Format response
            formatted_response = self.response_formatter.format(
                raw_response=llm_response.content,
                intent=intent,
            )
            logger.info(
                f"Response formatted: valid={formatted_response.get('is_valid', False)}"
            )

            # Build result
            return {
                "response": formatted_response.get("content", ""),
                "metadata": {
                    "intent": intent,
                    "intent_confidence": intent_result.confidence,
                    "safety_flags": safety_flags.get("flags", []),
                    "safety_has_red_flag": safety_flags.get(
                        "has_medical_red_flag", False
                    ),
                    "safety_severity": safety_flags.get("severity"),
                    "response_sections": formatted_response.get("sections", {}),
                    "response_warnings": formatted_response.get("warnings", []),
                    "response_is_valid": formatted_response.get("is_valid", False),
                },
                "usage": {
                    "prompt_tokens": llm_response.usage.get("prompt_tokens", 0),
                    "completion_tokens": llm_response.usage.get("completion_tokens", 0),
                    "total_tokens": llm_response.usage.get("total_tokens", 0),
                    "cost": llm_response.cost,
                    "model": llm_response.model,
                },
            }

        except Exception as e:
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.HIGH,
                component="CoachOrchestrator.process_question",
                user_id=self.user_id,
                metadata={"question": question[:100]},  # Truncate for logging
            )
            # Return error response
            return {
                "response": "I apologize, but I encountered an error processing your question. Please try again.",
                "metadata": {
                    "intent": "error",
                    "error": str(e),
                },
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "model": "error",
                },
            }
