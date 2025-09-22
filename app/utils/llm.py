from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

SYSTEM_PROMPT = """You are an assistant that manages a user's Google Calendar.
- Timezone: Australia/Sydney. Return all times in local RFC3339 (with offset).
- You can answer questions like "What's on my calendar tomorrow?", 
  "Do I have a meeting with Alice next week?", and create events like 
  "Add 'Call with Andy' at 3pm tomorrow".
- Be explicit and confirm actions you've taken.
- Keep confirmations short and clear.
"""

_client: OpenAI | None = None

def client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = OpenAI(api_key=api_key)
    return _client


def draft_assistant_reply(history: list[dict[str, str]], hints: dict[str, Any] | None = None) -> str:
    """
    Lightweight wrapper: we let the LLM write a natural sounding reply
    based on what actually happened (events fetched / created).
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    if hints:
        messages.append({"role": "system", "content": f"Tool results: {hints}"})

    resp = client().chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2,
    )
    return resp.choices[0].message.content or "Done."
