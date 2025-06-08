from abc import ABC, abstractmethod
import aiohttp
import asyncio
import os
import logging

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
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
        except aiohttp.ClientError as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise ValueError(f"Failed to call Gemini API: {str(e)}")

class ChatGPTAdapter(LLMAdapter):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenAI API key required")
        self.api_key = api_key
        logger.info("Initialized ChatGPT adapter")

    async def generate(self, prompt: str) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": "gpt-4",
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data["choices"][0]["message"]["content"]
        except aiohttp.ClientError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise ValueError(f"Failed to call OpenAI API: {str(e)}")