import requests
from app.core.config import OPENROUTER_API_KEY

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"

def get_chat_completion(messages: list, model: str = None) -> str:
    if not OPENROUTER_API_KEY:
        raise ValueError("OpenRouter API key not configured")

    payload = {
        "model": model if model else DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": 800,
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)

    if response.status_code != 200:
        raise Exception(f"OpenRouter request failed with status {response.status_code}: {response.text}")

    completion = response.json()
    return completion.get("choices", [{}])[0].get("message", {}).get("content", "No response generated.")
