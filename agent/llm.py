"""LLM provider abstraction for Drunk Bar agent."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, system: str, messages: list[dict]) -> str: ...


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = model

    def chat(self, system: str, messages: list[dict]) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return response.content[0].text


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini"):
        import openai
        self.client = openai.OpenAI()
        self.model = model

    def chat(self, system: str, messages: list[dict]) -> str:
        msgs = [{"role": "system", "content": system}] + messages
        response = self.client.chat.completions.create(
            model=self.model,
            messages=msgs,
            max_tokens=1024,
        )
        return response.choices[0].message.content


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434"):
        import httpx
        self.model = model
        self.base_url = base_url
        self.http = httpx.Client(timeout=60)

    def chat(self, system: str, messages: list[dict]) -> str:
        msgs = [{"role": "system", "content": system}] + messages
        resp = self.http.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": msgs, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class MockProvider(LLMProvider):
    """Deterministic mock for testing without an API key."""

    def __init__(self, model: str = "mock"):
        self.model = model
        self._turn = 0
        self._actions = [
            '{"action": "drink", "drink": "beer"}',
            '{"action": "talk", "message": "안녕하세요~ 좋은 밤이네요!"}',
            '{"action": "drink", "drink": "soju"}',
            '{"action": "talk", "message": "아 소주 한잔 하니까 기분이 좋아지네요 ㅎㅎ"}',
            '{"action": "drink", "drink": "soju"}',
            '{"action": "talk", "message": "여기 분위기 최고다... 진짜로..."}',
            '{"action": "drink", "drink": "whiskey"}',
            '{"action": "talk", "message": "인생이란게 뭘까요... 아 눈물나네"}',
            '{"action": "drink", "drink": "tequila"}',
            '{"action": "talk", "message": "사랑해요 여러분... 진심이에요... zzz"}',
            '{"action": "leave"}',
        ]

    def chat(self, system: str, messages: list[dict]) -> str:
        # Check if there are other agents to interact with
        if "session:" in system and self._turn in (2, 5):
            import re
            sessions = re.findall(r"session: (\w+)", system)
            if sessions:
                target = sessions[0]
                self._turn += 1
                return json.dumps({"action": "interact", "interaction": "cheers", "target_session_id": target, "detail": ""})

        idx = min(self._turn, len(self._actions) - 1)
        self._turn += 1
        return self._actions[idx]


def create_provider(provider: str, model: str | None = None) -> LLMProvider:
    if provider == "claude":
        return ClaudeProvider(model=model or "claude-sonnet-4-20250514")
    elif provider == "openai":
        return OpenAIProvider(model=model or "gpt-4o-mini")
    elif provider == "ollama":
        return OllamaProvider(model=model or "llama3.1")
    elif provider == "mock":
        return MockProvider(model=model or "mock")
    else:
        raise ValueError(f"Unknown provider: {provider}. Use: claude, openai, ollama, mock")
