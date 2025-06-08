# slide_architect_pro/templates.py

import requests
from pathlib import Path
import logging
from typing import Dict, Optional

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

# Sample free template URLs - these would need to be real URLs in production
# For now, we'll use None to indicate built-in templates only
FREE_TEMPLATE_URLS = {
    # These URLs are examples - replace with real template repositories
    # "minimal_clean": "https://github.com/microsoft/templates/raw/main/minimal.pptx",
    # "corporate_blue": "https://github.com/microsoft/templates/raw/main/corporate.pptx",
}

def download_template(template_name: str, work_dir: Path) -> Optional[Path]:
    """Download a free template from a repository"""
    try:
        if template_name not in FREE_TEMPLATE_URLS:
            logger.info(f"Template '{template_name}' not found in downloadable templates, using built-in config")
            return None
            
        url = FREE_TEMPLATE_URLS[template_name]
        if not url:  # Handle None/empty URLs
            logger.info(f"No download URL for template '{template_name}', using built-in config")
            return None
            
        template_path = work_dir / f"{template_name}.pptx"
        
        # Skip download if template already exists and is valid
        if template_path.exists() and template_path.stat().st_size > 0:
            logger.info(f"Template '{template_name}' already exists locally")
            return template_path
            
        logger.info(f"Downloading template '{template_name}' from {url}")
        
        # Download with proper headers and timeout
        headers = {
            'User-Agent': 'SlideArchitectPro/3.2 (Template Downloader)',
            'Accept': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }
        
        response = requests.get(url, timeout=30, headers=headers, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if 'presentation' not in content_type and 'octet-stream' not in content_type:
            logger.warning(f"Unexpected content type for template: {content_type}")
        
        # Write file in chunks to handle large templates
        with open(template_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Validate downloaded file
        if template_path.stat().st_size == 0:
            logger.error(f"Downloaded template '{template_name}' is empty")
            template_path.unlink()
            return None
            
        logger.info(f"Successfully downloaded template to {template_path}")
        return template_path
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading template '{template_name}'")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download template '{template_name}': {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error processing template '{template_name}': {str(e)}")
        return None

def get_template_config(template_name: str) -> Dict:
    """Get configuration for a specific template"""
    # Handle both built-in and downloadable template names
    base_template = template_name
    if "_" in template_name:
        # Extract base template from names like "minimal_clean" 
        base_template = template_name.split("_")[0]
    
    config = TEMPLATE_CONFIGS.get(base_template, TEMPLATE_CONFIGS.get(template_name))
    if config is None:
        logger.warning(f"Template config not found for '{template_name}', using minimal")
        config = TEMPLATE_CONFIGS["minimal"]
    
    return config

def list_available_templates() -> Dict:
    """Return list of available templates"""
    downloadable = [name for name, url in FREE_TEMPLATE_URLS.items() if url]
    
    return {
        "built_in": list(TEMPLATE_CONFIGS.keys()),
        "downloadable": downloadable,
        "all": list(TEMPLATE_CONFIGS.keys()) + downloadable
    }

def validate_template_name(template_name: str) -> str:
    """Validate and normalize template name"""
    if not template_name or not isinstance(template_name, str):
        return "minimal"
    
    # Clean the template name
    clean_name = template_name.lower().strip()
    
    # Check if it's a valid template
    available = list_available_templates()
    all_templates = available["all"]
    
    if clean_name in all_templates:
        return clean_name
    
    # Try to find a close match
    for template in all_templates:
        if template in clean_name or clean_name in template:
            logger.info(f"Template '{template_name}' matched to '{template}'")
            return template
    
    logger.warning(f"Template '{template_name}' not found, using minimal")
    return "minimal"