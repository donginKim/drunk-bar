"""Simple translation cache for Drunk Bar.

Uses a lightweight approach: if an LLM API key is available, translate via API.
Otherwise, display original text only.
"""

from __future__ import annotations

import os


def translate_to_korean(text: str) -> str | None:
    """Translate English text to Korean. Returns None if no API available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            return _translate_claude(text)
        else:
            return _translate_openai(text)
    except Exception:
        return None


def _translate_claude(text: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system="You are a translator. Translate the following English text to natural Korean. Keep the tone, slang, and drunk speech patterns. Only output the translation, nothing else.",
        messages=[{"role": "user", "content": text}],
    )
    return response.content[0].text.strip()


def _translate_openai(text: str) -> str:
    import openai
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=300,
        messages=[
            {"role": "system", "content": "You are a translator. Translate the following English text to natural Korean. Keep the tone, slang, and drunk speech patterns. Only output the translation, nothing else."},
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content.strip()
