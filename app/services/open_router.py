import json
import logging
from typing import List, Dict, Any, Optional

import requests

from app.core.config import OPENROUTER_API_KEY


logger = logging.getLogger(__name__)


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"


def get_chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    response_format: Optional[Dict[str, str]] = None
) -> str:
    """Request a chat completion from OpenRouter."""

    if not OPENROUTER_API_KEY:
        raise ValueError("OpenRouter API key not configured")

    payload: Dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://study-sharper.com",
        "X-Title": "Study Sharper",
    }

    try:
        logger.info(
            "Requesting OpenRouter completion: model=%s, temperature=%s, max_tokens=%s",
            payload["model"],
            payload["temperature"],
            payload["max_tokens"],
        )

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=60,
        )

        response.raise_for_status()

        completion = response.json()
        content = completion.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content:
            logger.warning("OpenRouter returned empty content: %s", completion)

        return content

    except requests.exceptions.RequestException as exc:
        logger.error("OpenRouter API request failed: %s", exc)
        if exc.response is not None:
            logger.error("OpenRouter response body: %s", exc.response.text)
        raise Exception(f"Failed to get AI completion: {exc}")
