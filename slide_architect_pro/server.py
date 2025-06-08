from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Union
import asyncio
import logging
import uuid
import bleach
import os
import glob
from .core import SlideArchitectPro, SlideInput
from .llm_adapters import GeminiAdapter, ChatGPTAdapter

logger = logging.getLogger(__name__)

app = FastAPI(title="Slide Architect Pro MCP Server")

# Add CORS middleware for web frontend compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class ChatMessage(BaseModel):
    message: str
    llm_provider: str = "offline"
    api_key: Optional[str] = None

@app.websocket("/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    architect = SlideArchitectPro()
    
    try:
        while True:
            try:
                # Receive and parse message
                data = await websocket.receive_json()
                message = ChatMessage(**data)
                logger.info(f"Received chat message: {message.message}")

                # Create appropriate LLM adapter
                if message.llm_provider == "offline":
                    llm_adapter = "offline"
                elif message.llm_provider == "gemini":
                    if not message.api_key:
                        raise ValueError("API key required for Gemini")
                    llm_adapter = GeminiAdapter(message.api_key)
                elif message.llm_provider == "openai":
                    if not message.api_key:
                        raise ValueError("API key required for OpenAI")
                    llm_adapter = ChatGPTAdapter(message.api_key)
                else:
                    raise ValueError(f"Unsupported LLM provider: {message.llm_provider}")
                
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
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close()
        except:
            pass

@app.post("/chat")
async def chat_http(message: ChatMessage):
    logger.info(f"Received HTTP chat message: {message.message}")
    try:
        architect = SlideArchitectPro()
        
        # Create appropriate LLM adapter
        if message.llm_provider == "offline":
            llm_adapter = "offline"
        elif message.llm_provider == "gemini":
            if not message.api_key:
                raise HTTPException(status_code=400, detail="API key required for Gemini")
            llm_adapter = GeminiAdapter(message.api_key)
        elif message.llm_provider == "openai":
            if not message.api_key:
                raise HTTPException(status_code=400, detail="API key required for OpenAI")
            llm_adapter = ChatGPTAdapter(message.api_key)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported LLM provider: {message.llm_provider}")
        
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Slide Architect Pro"}

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Slide Architect Pro MCP Server",
        "version": "3.2.4",
        "endpoints": {
            "chat_http": "/chat",
            "chat_websocket": "/chat",
            "health": "/health",
            "download": "/download/{filename}"
        }
    }

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated files"""
    try:
        # Security: Only allow downloading from a specific directory
        # and only certain file types
        allowed_extensions = {'.pptx', '.md', '.json', '.png'}
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="File type not allowed")
        
        # Sanitize filename to prevent directory traversal
        safe_filename = os.path.basename(filename)
        
        # Look for file in work directories (this is simplified - in production
        # you'd want a more sophisticated file management system)
        potential_paths = []
        work_dir_base = os.getenv("SLIDE_WORK_DIR", "/tmp")
        
        # Search common work directory patterns
        import glob
        search_patterns = [
            os.path.join(work_dir_base, "slide_architect_pro_*", safe_filename),
            os.path.join("/tmp", "slide_architect_pro_*", safe_filename)
        ]
        
        for pattern in search_patterns:
            potential_paths.extend(glob.glob(pattern))
        
        if not potential_paths:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Use the most recently created file
        file_path = max(potential_paths, key=os.path.getctime)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine media type
        media_types = {
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.md': 'text/markdown',
            '.json': 'application/json',
            '.png': 'image/png'
        }
        
        media_type = media_types.get(file_ext, 'application/octet-stream')
        
        return FileResponse(
            path=file_path,
            filename=safe_filename,
            media_type=media_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")