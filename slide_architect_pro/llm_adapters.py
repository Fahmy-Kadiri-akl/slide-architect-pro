# slide_architect_pro/llm_adapters.py

from abc import ABC, abstractmethod
import aiohttp
import asyncio
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LLMAdapter(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass

class GeminiAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Gemini API key required")
        self.api_key = api_key
        logger.info("Initialized Gemini adapter")

    async def generate(self, prompt: str) -> str:
        try:
            # Correct Gemini API endpoint with API key as query parameter
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{
                            "parts": [{"text": prompt}]
                        }],
                        "generationConfig": {
                            "temperature": 0.7,
                            "topK": 40,
                            "topP": 0.95,
                            "maxOutputTokens": 8192
                        }
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if "candidates" in data and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            return candidate["content"]["parts"][0]["text"]
                    
                    logger.error(f"Unexpected Gemini API response structure: {data}")
                    raise ValueError("Invalid response from Gemini API")
                    
        except aiohttp.ClientError as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise ValueError(f"Failed to call Gemini API: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in Gemini API call: {str(e)}")
            raise ValueError(f"Failed to call Gemini API: {str(e)}")

class ChatGPTAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenAI API key required")
        self.api_key = api_key
        logger.info("Initialized ChatGPT adapter")

    async def generate(self, prompt: str) -> str:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    json={
                        "model": "gpt-4",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 8192
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if "choices" in data and len(data["choices"]) > 0:
                        return data["choices"][0]["message"]["content"]
                    
                    logger.error(f"Unexpected OpenAI API response structure: {data}")
                    raise ValueError("Invalid response from OpenAI API")
                    
        except aiohttp.ClientError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise ValueError(f"Failed to call OpenAI API: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI API call: {str(e)}")
            raise ValueError(f"Failed to call OpenAI API: {str(e)}")