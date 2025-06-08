import uvicorn
import logging

logging.basicConfig(level=logging.INFO, filename="slide_architect_pro.log")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Slide Architect Pro MCP server")
    uvicorn.run(
        "slide_architect_pro.server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )