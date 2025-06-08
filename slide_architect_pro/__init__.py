# slide_architect_pro/__init__.py

"""
Slide Architect Pro - A secure, portable MCP server for generating professional slide decks via chat
"""

__version__ = "3.2.4"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .core import SlideArchitectPro, SlideInput
from .llm_adapters import LLMAdapter, GeminiAdapter, ChatGPTAdapter
from .templates import get_template_config, list_available_templates
from .renderers import render_vega_lite, validate_vega_spec

__all__ = [
    "SlideArchitectPro",
    "SlideInput", 
    "LLMAdapter",
    "GeminiAdapter",
    "ChatGPTAdapter",
    "get_template_config",
    "list_available_templates",
    "render_vega_lite",
    "validate_vega_spec"
]