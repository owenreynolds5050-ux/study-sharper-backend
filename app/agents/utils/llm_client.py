"""
Shared LLM Client for OpenRouter API
Handles all LLM calls with consistent error handling and token tracking
"""

import httpx
import os
from typing import Dict, Any, Optional, List
import json
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    """Shared client for making LLM calls via OpenRouter"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.default_model = "anthropic/claude-3.5-haiku"
        
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set - LLM calls will fail")
    
    async def call(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Make LLM API call via OpenRouter.
        
        Args:
            prompt: User prompt/message
            model: Model to use (defaults to Haiku)
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            json_mode: Force JSON response format
            
        Returns:
            Dictionary with content, tokens_used, and model
            
        Raises:
            Exception: If API call fails
        """
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Build payload
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        logger.debug(f"LLM call: model={payload['model']}, tokens={max_tokens}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://studysharper.com",  # Optional
                        "X-Title": "StudySharper"  # Optional
                    },
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                content = result["choices"][0]["message"]["content"]
                tokens_used = result.get("usage", {}).get("total_tokens", 0)
                model_used = result.get("model", payload["model"])
                
                logger.info(f"LLM response: {tokens_used} tokens, model={model_used}")
                
                return {
                    "content": content,
                    "tokens_used": tokens_used,
                    "model": model_used
                }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LLM API error: {e.response.status_code}")
        except httpx.TimeoutException:
            logger.error("LLM API timeout")
            raise Exception("LLM API timeout after 30s")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    async def call_with_history(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Make LLM call with full message history.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dictionary with content, tokens_used, and model
        """
        
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")
        
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        logger.debug(f"LLM call with history: {len(messages)} messages")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "content": result["choices"][0]["message"]["content"],
                    "tokens_used": result.get("usage", {}).get("total_tokens", 0),
                    "model": result.get("model", payload["model"])
                }
        
        except Exception as e:
            logger.error(f"LLM call with history failed: {e}")
            raise


# Global instance
llm_client = LLMClient()
