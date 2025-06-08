# slide_architect_pro/templates.py

import requests
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

SLIDE_ARCHITECT_PROMPT_V3_2 = """
You are an expert slide architect. Generate professional slide decks in markdown format.

INSTRUCTIONS:
- Create 5-8 slides maximum
- Follow story structure: Hook → Problem → Solution → Conclusion
- Include engaging visuals (charts, diagrams)
- Make content accessible with alt text
- Use clear, concise bullet points
- Include speaker notes and engagement techniques

OUTPUT FORMAT:
Use this exact markdown structure:

# Slide 1 - Title Slide
**Title:** [Main title]
**Subtitle:** [Context/tagline]
**Logo:** Top-right corner
**Slide Notes:** [Speaker notes for this slide]
**Engagement Techniques:** [How to engage audience]

# Slide 2 - Hook/Problem
**Title:** [Slide title]
**Body:**
- [Key point 1]
- [Key point 2]
- [Key point 3]
**Visual:** [Description of visual element]
```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": [{"category": "A", "value": 30}, {"category": "B", "value": 55}]},
  "mark": "bar",
  "encoding": {
    "x": {"field": "category", "type": "nominal"},
    "y": {"field": "value", "type": "quantitative"}
  }
}
```
**Alt Text:** [Accessibility description of visual]
**Slide Notes:** [Speaker notes]
**Engagement Techniques:** [Audience engagement ideas]

For diagrams, use Mermaid syntax:
```mermaid
sequenceDiagram
    participant User
    participant System
    User->>System: Login Request
    System-->>User: Authentication Token
```

TONE & STYLE GUIDELINES:
- Executives: Formal, data-driven, ROI-focused
- Investors: Compelling, market-focused, growth potential
- Sales Team: Energetic, benefit-focused, action-oriented
- Developers: Technical, detailed, implementation-focused
- Training: Educational, step-by-step, interactive

Generate slides that match the specified audience, context, and key message.
"""

# Template configurations for python-pptx
TEMPLATE_CONFIGS = {
    "minimal": {
        "font_family": "Arial",
        "title_font_size": 24,
        "body_font_size": 18,
        "colors": {
            "title": (0, 0, 0),  # Black
            "body": (64, 64, 64),  # Dark gray
            "background": (255, 255, 255),  # White
            "accent": (0, 120, 215)  # Blue
        },
        "layout_preferences": {
            "title_slide": 0,
            "content_slide": 1,
            "two_column": 3,
            "blank": 6
        }
    },
    "corporate": {
        "font_family": "Calibri",
        "title_font_size": 28,
        "body_font_size": 20,
        "colors": {
            "title": (0, 51, 102),  # Navy blue
            "body": (51, 51, 51),  # Dark gray
            "background": (248, 248, 248),  # Light gray
            "accent": (0, 176, 80)  # Green
        },
        "layout_preferences": {
            "title_slide": 0,
            "content_slide": 1,
            "two_column": 3,
            "blank": 6
        }
    },
    "bold": {
        "font_family": "Arial Black",
        "title_font_size": 32,
        "body_font_size": 22,
        "colors": {
            "title": (192, 0, 0),  # Red
            "body": (0, 0, 0),  # Black
            "background": (255, 255, 240),  # Light yellow
            "accent": (255, 165, 0)  # Orange
        },
        "layout_preferences": {
            "title_slide": 0,
            "content_slide": 1,
            "two_column": 3,
            "blank": 6
        }
    }
}

# Free template URLs (GitHub repositories)
FREE_TEMPLATE_URLS = {
    "minimal_clean": "https://raw.githubusercontent.com/daveebbelaar/powerpoint-templates/main/minimal-clean.pptx",
    "corporate_blue": "https://raw.githubusercontent.com/daveebbelaar/powerpoint-templates/main/corporate-blue.pptx",
    "modern_gradient": "https://raw.githubusercontent.com/daveebbelaar/powerpoint-templates/main/modern-gradient.pptx",
    "startup_pitch": "https://raw.githubusercontent.com/daveebbelaar/powerpoint-templates/main/startup-pitch.pptx"
}

def download_template(template_name: str, work_dir: Path) -> Path:
    """Download a free template from GitHub repository"""
    try:
        if template_name not in FREE_TEMPLATE_URLS:
            logger.warning(f"Template '{template_name}' not found in free templates")
            return None
            
        url = FREE_TEMPLATE_URLS[template_name]
        template_path = work_dir / f"{template_name}.pptx"
        
        # Skip download if template already exists
        if template_path.exists():
            logger.info(f"Template '{template_name}' already exists locally")
            return template_path
            
        logger.info(f"Downloading template '{template_name}' from {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with open(template_path, "wb") as f:
            f.write(response.content)
            
        logger.info(f"Successfully downloaded template to {template_path}")
        return template_path
        
    except requests.RequestException as e:
        logger.error(f"Failed to download template '{template_name}': {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error processing template '{template_name}': {str(e)}")
        return None

def get_template_config(template_name: str) -> dict:
    """Get configuration for a specific template"""
    return TEMPLATE_CONFIGS.get(template_name, TEMPLATE_CONFIGS["minimal"])

def list_available_templates() -> dict:
    """Return list of available templates"""
    return {
        "built_in": list(TEMPLATE_CONFIGS.keys()),
        "downloadable": list(FREE_TEMPLATE_URLS.keys())
    }