import uvicorn
import logging
import sys
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("slide_architect_pro.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Slide Architect Pro MCP server")
    try:
        uvicorn.run(
            "slide_architect_pro.server:app",
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=False
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)