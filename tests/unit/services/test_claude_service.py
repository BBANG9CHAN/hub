from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import TextBlock

from hub.services.claude_service import ClaudeService, _load_prompt


def _make_mock_client(text: str) -> MagicMock:
    content = MagicMock()
    content.text = text
    content.__class__ = TextBlock  # isinstance(content, TextBlock) → True

    response = MagicMock()
    response.content = [content]
    response.usage.input_tokens = 10
    response.usage.output_tokens = 20

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


async def test_generate_returns_text() -> None:
    client = _make_mock_client("Hello!")
    with patch("hub.services.claude_service.AsyncAnthropic", return_value=client):
        svc = ClaudeService(api_key="test-key")
        result = await svc.generate("Say hello")
    assert result == "Hello!"


async def test_generate_passes_system_prompt() -> None:
    client = _make_mock_client("ok")
    with patch("hub.services.claude_service.AsyncAnthropic", return_value=client):
        svc = ClaudeService(api_key="test-key")
        await svc.generate("prompt", system="You are a helper")

    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "You are a helper"


async def test_generate_without_system_omits_key() -> None:
    client = _make_mock_client("ok")
    with patch("hub.services.claude_service.AsyncAnthropic", return_value=client):
        svc = ClaudeService(api_key="test-key")
        await svc.generate("prompt")

    call_kwargs = client.messages.create.call_args.kwargs
    assert "system" not in call_kwargs


async def test_generate_blog_draft_uses_prompt_file(tmp_path: Path) -> None:
    (tmp_path / "blog_post_generation.md").write_text("system prompt", encoding="utf-8")
    client = _make_mock_client("draft content")
    with patch("hub.services.claude_service.AsyncAnthropic", return_value=client), \
         patch("hub.services.claude_service._PROMPTS_DIR", tmp_path):
        svc = ClaudeService(api_key="test-key")
        result = await svc.generate_blog_draft("topic", "my notes")

    assert result == "draft content"
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "system prompt"


async def test_generate_blog_draft_formats_user_message(tmp_path: Path) -> None:
    (tmp_path / "blog_post_generation.md").write_text("sys", encoding="utf-8")
    client = _make_mock_client("ok")
    with patch("hub.services.claude_service.AsyncAnthropic", return_value=client), \
         patch("hub.services.claude_service._PROMPTS_DIR", tmp_path):
        svc = ClaudeService(api_key="test-key")
        await svc.generate_blog_draft("제목", "메모 내용")

    messages = client.messages.create.call_args.kwargs["messages"]
    assert "제목" in messages[0]["content"]
    assert "메모 내용" in messages[0]["content"]


def test_load_prompt_raises_if_missing(tmp_path: Path) -> None:
    with patch("hub.services.claude_service._PROMPTS_DIR", tmp_path):
        with pytest.raises(FileNotFoundError):
            _load_prompt("nonexistent.md")


def test_load_prompt_returns_content(tmp_path: Path) -> None:
    (tmp_path / "test.md").write_text("hello", encoding="utf-8")
    with patch("hub.services.claude_service._PROMPTS_DIR", tmp_path):
        assert _load_prompt("test.md") == "hello"
