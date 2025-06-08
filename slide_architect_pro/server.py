from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import asyncio
import logging
import uuid
import bleach
from .core import SlideArchitectPro, SlideInput
from .llm_adapters import GeminiAdapter, ChatGPTAdapter

logger = logging.getLogger(__name__)

app = FastAPI(title="Slide Architect Pro MCP Server")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class ChatMessage(BaseModel):
    message: str
    llm_provider: str = "offline"
    api_key: str | None = None

@app.websocket("/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    architect = SlideArchitectPro()
    try:
        while True:
            data = await websocket.receive_json()
            message = ChatMessage(**data)
            logger.info(f"Received chat message: {message.message}")

            try:
                llm_adapter = message.llm_provider if message.llm_provider == "offline" else (
                    GeminiAdapter(message.api_key) if message.llm_provider == "gemini" else
                    ChatGPTAdapter(message.api_key)
                )
                input_data = await architect.parse_chat_message(message.message, llm_adapter)
                result = await architect.generate_deck(input_data, llm_adapter)
                response = {
                    "id": str(uuid.uuid4()),
                    "message": f"Your slide deck '{input_data.topic}' is ready! Download PowerPoint: {result['pptx_file']}, Markdown: {result['md_file']}, JSON: {result['json_file']}",
                    "files": {
                        "pptx": result["pptx_file"],
                        "markdown": result["md_file"],
                        "json": result["json_file"]
                    }
                }
                await websocket.send_json(response)
            except Exception as e:
                logger.error(f"Error processing chat message: {str(e)}")
                await websocket.send_json({
                    "id": str(uuid.uuid4()),
                    "message": f"Error: {str(e)}",
                    "error": True
                })
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.close()

@app.post("/chat")
async def chat_http(message: ChatMessage):
    logger.info(f"Received HTTP chat message: {message.message}")
    try:
        architect = SlideArchitectPro()
        llm_adapter = message.llm_provider if message.llm_provider == "offline" else (
            GeminiAdapter(message.api_key) if message.llm_provider == "gemini" else
            ChatGPTAdapter(message.api_key)
        )
        input_data = await architect.parse_chat_message(message.message, llm_adapter)
        result = await architect.generate_deck(input_data, llm_adapter)
        return {
            "id": str(uuid.uuid4()),
            "message": f"Your slide deck '{input_data.topic}' is ready! Download PowerPoint: {result['pptx_file']}, Markdown: {result['md_file']}, JSON: {result['json_file']}",
            "files": {
                "pptx": result["pptx_file"],
                "markdown": result["md_file"],
                "json": result["json_file"]
            }
        }
    except Exception as e:
        logger.error(f"Error processing HTTP chat message: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))