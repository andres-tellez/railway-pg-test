import json
import pytest
from unittest.mock import Mock


def test_factory_returns_fake_by_default(monkeypatch):
    from src.services.training_plan.llm_factory import create_llm_client

    monkeypatch.delenv("TRAINING_PLAN_LLM_PROVIDER", raising=False)
    monkeypatch.setenv(
        "FAKE_LLM_JSON_RESPONSE",
        '{"plan_name":"FromEnv","weeks":[{"week_number":1,"workouts":[{"day":"Mon","workout_type":"Easy Run","distance_miles":3.0}]}]}',
    )

    client = create_llm_client()
    out = client.completion([], {})
    data = json.loads(out)
    assert data["plan_name"] == "FromEnv"


def test_factory_returns_openai_adapter(monkeypatch):
    from src.services.training_plan.llm_factory import create_llm_client
    from src.services.training_plan.llm_adapters.openai_adapter import (
        OpenAIClientAdapter,
    )

    monkeypatch.setenv("TRAINING_PLAN_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    client = create_llm_client()
    assert isinstance(client, OpenAIClientAdapter)


def test_openai_adapter_calls_api_with_mocked_client():
    from src.services.training_plan.llm_adapters.openai_adapter import (
        OpenAIClientAdapter,
    )

    # Mock OpenAI response structure
    mock_message = Mock()
    mock_message.content = '{"plan_name":"Test","weeks":[{"week_number":1,"workouts":[{"day":"Mon","workout_type":"Easy Run","distance_miles":3.0}]}]}'

    mock_choice = Mock()
    mock_choice.message = mock_message

    mock_usage = Mock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.total_tokens = 150

    mock_response = Mock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    # Mock client
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response

    # Create adapter with mocked client
    adapter = OpenAIClientAdapter(client=mock_client)

    # Call completion
    messages = [{"role": "system", "content": "You are a coach"}]
    config = {
        "model": "gpt-4",
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }

    result = adapter.completion(messages, config)

    # Verify API was called correctly
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "gpt-4"
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert call_kwargs["messages"] == messages

    # Verify result
    data = json.loads(result)
    assert data["plan_name"] == "Test"


def test_openai_adapter_handles_empty_response():
    from src.services.training_plan.llm_adapters.openai_adapter import (
        OpenAIClientAdapter,
    )

    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = []  # Empty response
    mock_client.chat.completions.create.return_value = mock_response

    adapter = OpenAIClientAdapter(client=mock_client)

    with pytest.raises(ValueError, match="Empty response"):
        adapter.completion([], {})


def test_openai_adapter_handles_none_content():
    from src.services.training_plan.llm_adapters.openai_adapter import (
        OpenAIClientAdapter,
    )

    mock_message = Mock()
    mock_message.content = None

    mock_choice = Mock()
    mock_choice.message = mock_message

    mock_response = Mock()
    mock_response.choices = [mock_choice]

    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response

    adapter = OpenAIClientAdapter(client=mock_client)

    with pytest.raises(ValueError, match="None content"):
        adapter.completion([], {})
