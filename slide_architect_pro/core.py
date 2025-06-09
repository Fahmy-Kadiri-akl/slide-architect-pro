# slide_architect_pro/core.py

import asyncio
import json
import os
import mistune
import bleach
import tempfile
import stat
import uuid
import re
import logging
from pathlib import Path
from typing import Optional, Dict, List, Union, Any
from pydantic import BaseModel, field_validator
from python_pptx import Presentation
from python_pptx.util import Inches, Pt
from python_pptx.enum.text import PP_ALIGN
from python_pptx.dml.color import RGBColor
from .llm_adapters import LLMAdapter
from .templates import SLIDE_ARCHITECT_PROMPT_V3_2, TEMPLATE_CONFIGS, download_template, get_template_config
from .renderers import render_vega_lite

logger = logging.getLogger(__name__)

class SlideInput(BaseModel):
    topic: str = "Untitled Presentation"
    audience: str = "General"
    context: str = "Business presentation"
    key_message: str = "Take action"
    tone: Optional[str] = None
    style: Optional[str] = None
    template: str = "minimal"

    @field_validator("*", mode="before")
    @classmethod
    def sanitize_input(cls, v: Any) -> Any:
        if isinstance(v, str):
            # Clean HTML and limit length
            cleaned = bleach.clean(v, tags=[], strip=True)
            if len(cleaned) > 1000:
                raise ValueError("Input too long (max 1000 characters)")
            # Allow international characters but block dangerous patterns
            if re.search(r'[<>{}\\`]', cleaned):
                raise ValueError("Invalid characters detected")
            return cleaned
        return v

class SlideRenderer(mistune.HTMLRenderer):
    def __init__(self):
        super().__init__(escape=False)
        self.slides = []
        self.current_slide = None
        self.section = None

    def heading(self, text: str, level: int, **attrs) -> str:
        text = bleach.clean(text, tags=[], strip=True)
        if level == 1 and text.startswith("Slide "):
            if self.current_slide:
                self.slides.append(self.current_slide)
            self.current_slide = {
                "title": "",
                "content": [],
                "visuals": [],
                "notes": [],
                "engagement": [],
                "alt_text": [],
                "type": "standard"
            }
            self.section = "title"
            return ""
        return super().heading(text, level, **attrs)

    def paragraph(self, text: str) -> str:
        text = bleach.clean(text, tags=[], strip=True)
        if not self.current_slide:
            return ""
        if text.startswith("**Title:**"):
            self.current_slide["title"] = text.replace("**Title:**", "").strip()
        elif text.startswith("**Body:**"):
            self.section = "content"
        elif text.startswith("**Visual:**"):
            self.section = "visuals"
            self.current_slide["type"] = "chart" if "vega" in text.lower() else "diagram" if "mermaid" in text.lower() else "standard"
        elif text.startswith("**Alt Text:**"):
            self.section = "alt_text"
            self.current_slide["alt_text"].append(text.replace("**Alt Text:**", "").strip())
        elif text.startswith("**Slide Notes:**"):
            self.section = "notes"
        elif text.startswith("**Engagement Techniques:**"):
            self.section = "engagement"
        elif self.section in ["notes", "engagement"]:
            self.current_slide[self.section].append(text.strip())
        return ""

    def list_item(self, text: str) -> str:
        text = bleach.clean(text, tags=[], strip=True)
        if self.section == "content":
            self.current_slide["content"].append(text.strip())
        return ""

    def block_code(self, code: str, info: Optional[str] = None) -> str:
        if self.section == "visuals":
            if info in ["json", "mermaid", "plantuml", "latex"]:
                code = bleach.clean(code, tags=[], strip=True)
                # Security: Limit code block size and complexity
                if len(code) > 5000:
                    logger.warning(f"Code block too large ({len(code)} chars)")
                    return ""
                if info == "mermaid" and len(code.split("\n")) > 20:
                    logger.warning("Mermaid diagram too complex")
                    return ""
                self.current_slide["visuals"].append({"code": code, "lang": info or "text"})
            else:
                logger.warning(f"Unsupported code block language: {info}")
        return ""

    def finish(self) -> List[Dict[str, Any]]:
        if self.current_slide:
            self.slides.append(self.current_slide)
        return self.slides

class SlideArchitectPro:
    def __init__(self):
        self.prompt = SLIDE_ARCHITECT_PROMPT_V3_2 + "\n\n### Additional Instructions\n- For diagram requests (e.g., sequence diagram, flowchart), generate a valid Mermaid code block tailored to the slide's context. Ensure the diagram is concise (≤10 nodes) and includes a descriptive alt text."
        self._setup_work_directory()
        self.templates = TEMPLATE_CONFIGS

    def _setup_work_directory(self):
        """Securely setup work directory with proper validation"""
        work_dir_path = os.getenv("SLIDE_WORK_DIR")
        
        if work_dir_path:
            # Validate the path is safe
            work_dir_path = os.path.abspath(work_dir_path)
            # Only allow specific safe directories
            allowed_prefixes = ["/tmp", "/var/tmp", tempfile.gettempdir()]
            if not any(work_dir_path.startswith(prefix) for prefix in allowed_prefixes):
                logger.warning(f"Unsafe work directory: {work_dir_path}")
                work_dir_path = None
        
        if not work_dir_path:
            work_dir_path = os.path.join(tempfile.gettempdir(), f"slide_architect_pro_{uuid.uuid4()}")
        
        self.work_dir = Path(work_dir_path)
        
        try:
            self.work_dir.mkdir(parents=True, exist_ok=True)
            # Test write permissions
            test_file = self.work_dir / ".test_write"
            test_file.touch()
            test_file.unlink()
            logger.info(f"Work directory setup: {self.work_dir}")
        except (PermissionError, OSError) as e:
            logger.error(f"Cannot setup work directory {self.work_dir}: {e}")
            raise ValueError(f"Cannot setup work directory: {e}")

    async def generate_deck(self, input_data: SlideInput, llm_adapter: Union[LLMAdapter, str]) -> Dict[str, Any]:
        try:
            # Map audience to tone/style if not specified
            tone_style_map = {
                "Executives": {"tone": "Formal", "style": "Clean & minimal"},
                "Investors": {"tone": "Investor-facing", "style": "Clean & minimal"},
                "Sales Team": {"tone": "Energetic", "style": "Bold & colorful"},
                "Developers/Engineers": {"tone": "Technical", "style": "Data-driven"},
                "Internal Training": {"tone": "Energetic", "style": "Visual-first"}
            }
            
            tone = input_data.tone
            style = input_data.style
            if not tone or not style:
                for aud, settings in tone_style_map.items():
                    if aud.lower() in input_data.audience.lower():
                        tone = tone or settings["tone"]
                        style = style or settings["style"]
                        break
                tone = tone or "Professional"
                style = style or "Clean & minimal"

            user_prompt = f"""
Topic: {input_data.topic}
Audience: {input_data.audience}
Context: {input_data.context}
Key Message: {input_data.key_message}
Tone: {tone}
Style: {style}
"""
            full_prompt = self.prompt + "\n\n" + user_prompt

            # Generate content based on LLM adapter type
            if isinstance(llm_adapter, str) and llm_adapter == "offline":
                markdown_output = self._offline_response(full_prompt, input_data)
            else:
                try:
                    markdown_output = await llm_adapter.generate(full_prompt)
                    if len(markdown_output) > 100_000:
                        logger.warning("LLM response too large")
                        raise ValueError("LLM response exceeds maximum size")
                    markdown_output = bleach.clean(markdown_output, tags=["pre", "code"], strip=True)
                except Exception as llm_error:
                    logger.error(f"LLM generation failed: {llm_error}")
                    logger.info("Falling back to offline mode")
                    markdown_output = self._offline_response(full_prompt, input_data)

            # Convert to JSON and validate
            json_output = self._convert_markdown_to_json(markdown_output)
            self._validate_automation_edge_cases(json_output)

            # Generate files
            pptx_file = await self._generate_pptx(json_output, input_data.topic, input_data.template)
            
            # Save markdown and JSON files
            safe_filename = re.sub(r'[^\w\-_\. ]', '_', input_data.topic).replace(' ', '_')
            md_file = self.work_dir / f"{safe_filename}.md"
            json_file = self.work_dir / f"{safe_filename}.json"
            
            with md_file.open("w", encoding="utf-8") as f:
                f.write(markdown_output)
            with json_file.open("w", encoding="utf-8") as f:
                json.dump(json_output, f, indent=2)

            return {
                "markdown": markdown_output,
                "json": json_output,
                "pptx_file": str(pptx_file),
                "md_file": str(md_file),
                "json_file": str(json_file)
            }
        except Exception as e:
            logger.error(f"Error generating deck: {str(e)}")
            raise ValueError(f"Failed to generate slide deck: {str(e)}")

    async def parse_chat_message(self, message: str, llm_adapter: Union[LLMAdapter, str]) -> SlideInput:
        try:
            message = bleach.clean(message, tags=[], strip=True)
            if len(message) > 5000:
                raise ValueError("Message too long (max 5000 characters)")
                
            if isinstance(llm_adapter, str) and llm_adapter == "offline":
                return self._regex_parse_chat_message(message)

            intent_prompt = f"""
Parse the following chat message into a JSON object with fields: topic, audience, context, key_message, tone, style, template.
If a field is not specified, use default values: topic="Untitled Presentation", audience="General", context="Business presentation", key_message="Take action", tone=null, style=null, template="minimal".
Ensure the output is valid JSON with no additional text.

Message: {message}

Output only valid JSON:
"""
            try:
                intent_output = await llm_adapter.generate(intent_prompt)
                if len(intent_output) > 10_000:
                    logger.warning("Intent extraction response too large")
                    return self._regex_parse_chat_message(message)
            except Exception as llm_error:
                logger.warning(f"LLM intent extraction failed: {llm_error}")
                return self._regex_parse_chat_message(message)

            try:
                # Extract JSON from response
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', intent_output, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    # Try to extract JSON without code blocks
                    json_match = re.search(r'\{.*\}', intent_output, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                    else:
                        json_str = intent_output.strip()
                
                intent_data = json.loads(json_str)
                return SlideInput(**intent_data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Invalid JSON from intent extraction: {e}")
                return self._regex_parse_chat_message(message)
        except Exception as e:
            logger.error(f"Error parsing chat message: {str(e)}")
            return self._regex_parse_chat_message(message)

    def _regex_parse_chat_message(self, message: str) -> SlideInput:
        """Fallback regex-based parsing for chat messages"""
        message = bleach.clean(message, tags=[], strip=True)
        topic = "Untitled Presentation"
        audience = "General"
        context = "Business presentation"
        key_message = "Take action"
        template = "minimal"

        # Extract topic
        topic_patterns = [
            r"generate.*?(?:for|about)\s+([^\,\n]+)",
            r"create.*?(?:for|about)\s+([^\,\n]+)",
            r"make.*?(?:for|about)\s+([^\,\n]+)"
        ]
        for pattern in topic_patterns:
            match = re.search(pattern, message, re.I)
            if match:
                topic = match.group(1).strip()
                break

        # Extract other fields
        field_patterns = {
            "audience": r"audience\s*[:=]\s*([^\,\n]+)",
            "context": r"context\s*[:=]\s*([^\,\n]+)",
            "key_message": r"(?:key message|cta)\s*[:=]\s*([^\,\n]+)",
            "template": r"template\s*[:=]\s*([^\,\n]+)"
        }
        
        for field, pattern in field_patterns.items():
            match = re.search(pattern, message, re.I)
            if match:
                if field == "audience":
                    audience = match.group(1).strip()
                elif field == "context":
                    context = match.group(1).strip()
                elif field == "key_message":
                    key_message = match.group(1).strip()
                elif field == "template":
                    template = match.group(1).strip()

        return SlideInput(
            topic=topic,
            audience=audience,
            context=context,
            key_message=key_message,
            template=template
        )

    def _offline_response(self, prompt: str, input_data: SlideInput) -> str:
        """Generate offline response when no LLM is available"""
        return f"""# Slide 1 - Title Slide  
**Title:** {input_data.topic}  
**Subtitle:** {input_data.context}  
**Logo:** Top-right corner  
**Slide Notes:** Introduce the topic and set the stage.  
**Engagement Techniques:** Share a compelling opening statement.

# Slide 2 - Agenda  
**Title:** Agenda  
**Body:**
- Hook: Why this matters
- Problem: Current challenges
- Solution: Our approach
- Conclusion: Next steps

# Slide 3 - Hook  
**Title:** Why This Matters  
**Body:**  
- Market opportunity is growing rapidly
- Current solutions are inadequate
- Time-sensitive opportunity
**Visual:** Vega-Lite chart  
```json
{{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {{"values": [{{"category": "Market Size", "value": 85}}, {{"category": "Growth Rate", "value": 45}}]}},
  "mark": "bar",
  "encoding": {{"x": {{"field": "category", "type": "nominal"}}, "y": {{"field": "value", "type": "quantitative"}}}}
}}
```  
**Alt Text:** Bar chart showing market opportunity metrics.  
**Slide Notes:** Emphasize the urgency and scale of opportunity.  
**Engagement Techniques:** Ask audience about their experience with this problem.

# Slide 4 - Solution  
**Title:** Our Solution  
**Body:**  
- Innovative approach that addresses core issues
- Proven technology with measurable results
- Scalable implementation pathway
**Visual:** Mermaid diagram  
```mermaid
sequenceDiagram
  participant User
  participant System
  participant Database
  User->>System: Submit Request
  System->>Database: Process Data
  Database-->>System: Return Results
  System-->>User: Deliver Solution
```  
**Alt Text:** Process flow diagram showing solution workflow.
**Slide Notes:** Walk through each step of the solution.
**Engagement Techniques:** Demonstrate with a real example.

# Slide 5 - Closing  
**Title:** Call to Action  
**Body:**  
- {input_data.key_message}
- Ready to move forward together
- Questions and next steps
**Slide Notes:** Summarize key benefits and invite action.  
**Engagement Techniques:** Open floor for questions and discussion.
"""

    def _convert_markdown_to_json(self, markdown_text: str) -> Dict[str, Any]:
        try:
            renderer = SlideRenderer()
            parser = mistune.create_markdown(renderer=renderer)
            parser(markdown_text)  # Parse the markdown
            slides = renderer.finish()  # Get the slides from renderer
            
            if not slides:
                logger.warning("No slides parsed from Markdown")
                raise ValueError("No slides parsed from Markdown")
            return {"slides": slides}
        except Exception as e:
            logger.error(f"Markdown parsing error: {str(e)}")
            raise ValueError(f"Failed to parse Markdown: {str(e)}")

    def _validate_automation_edge_cases(self, json_data: Dict[str, Any]):
        """Validate and clean up generated slide data"""
        if "slides" not in json_data or not isinstance(json_data["slides"], list):
            raise ValueError("Invalid slide data structure")
            
        for i, slide in enumerate(json_data["slides"]):
            if not isinstance(slide, dict):
                logger.warning(f"Invalid slide {i}, skipping")
                continue
                
            # Ensure required fields exist
            required_fields = ["title", "content", "visuals", "notes", "engagement", "alt_text", "type"]
            for field in required_fields:
                if field not in slide:
                    slide[field] = [] if field in ["content", "visuals", "notes", "engagement", "alt_text"] else ("standard" if field == "type" else "")
            
            try:
                visuals_to_remove = []
                for j, visual in enumerate(slide["visuals"]):
                    if not isinstance(visual, dict) or "lang" not in visual or "code" not in visual:
                        logger.warning(f"Invalid visual {j} in slide {i}")
                        visuals_to_remove.append(j)
                        continue
                        
                    if visual["lang"] == "json" and "vega" in visual["code"].lower():
                        try:
                            data = json.loads(visual["code"])
                            if "data" in data and "values" in data["data"]:
                                if len(data["data"]["values"]) > 50:
                                    logger.warning(f"Chart dataset exceeds 50 points in slide {slide['title']}")
                                    visuals_to_remove.append(j)
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(f"Invalid Vega-Lite JSON in slide {slide['title']}: {e}")
                            visuals_to_remove.append(j)
                    elif visual["lang"] in ["mermaid", "plantuml"]:
                        nodes = visual["code"].count("->") + visual["code"].count("-->>")
                        if nodes > 10:
                            logger.warning(f"Diagram too complex in slide {slide['title']}")
                            slide["notes"].append("Consider splitting complex diagram across multiple slides")
                    elif visual["lang"] == "python":
                        logger.warning(f"Python code block ignored in slide {slide['title']}")
                        visuals_to_remove.append(j)
                
                # Remove invalid visuals (in reverse order to maintain indices)
                for j in reversed(visuals_to_remove):
                    slide["visuals"].pop(j)
                    
            except Exception as e:
                logger.error(f"Validation error in slide {slide.get('title', i)}: {str(e)}")
                if isinstance(slide.get("notes"), list):
                    slide["notes"].append(f"Validation error: {str(e)}")
                else:
                    slide["notes"] = [f"Validation error: {str(e)}"]

    async def _generate_pptx(self, json_data: Dict[str, Any], title: str, template: str) -> Path:
        try:
            # Try to download template if it's a downloadable one (run in thread pool)
            import asyncio
            loop = asyncio.get_event_loop()
            template_file = await loop.run_in_executor(None, download_template, template, self.work_dir)
            
            if template_file and template_file.exists():
                logger.info(f"Using downloaded template: {template_file}")
                prs = Presentation(str(template_file))
            else:
                logger.info("Using default presentation template")
                prs = Presentation()
            
            template_config = get_template_config(template)
            safe_filename = re.sub(r'[^\w\-_\. ]', '_', title).replace(' ', '_')
            output_file = self.work_dir / f"{safe_filename}.pptx"

            for i, slide_data in enumerate(json_data["slides"]):
                try:
                    # Choose layout based on slide type and content - with safety checks
                    max_layouts = len(prs.slide_layouts)
                    
                    if i == 0:
                        layout_idx = min(template_config["layout_preferences"]["title_slide"], max_layouts - 1)
                    elif slide_data["type"] == "chart":
                        layout_idx = min(template_config["layout_preferences"]["blank"], max_layouts - 1)
                    elif slide_data["type"] == "diagram":
                        layout_idx = min(template_config["layout_preferences"]["blank"], max_layouts - 1)
                    elif "comparison" in slide_data["title"].lower():
                        layout_idx = min(template_config["layout_preferences"]["two_column"], max_layouts - 1)
                    elif slide_data["visuals"] and not slide_data["content"]:
                        layout_idx = min(template_config["layout_preferences"]["blank"], max_layouts - 1)
                    else:
                        layout_idx = min(template_config["layout_preferences"]["content_slide"], max_layouts - 1)

                    layout = prs.slide_layouts[layout_idx]
                    slide = prs.slides.add_slide(layout)
                    
                    # Set title
                    try:
                        if hasattr(slide, 'shapes') and hasattr(slide.shapes, 'title') and slide.shapes.title:
                            title_shape = slide.shapes.title
                            title_shape.text = slide_data["title"]
                            if hasattr(title_shape, 'text_frame') and title_shape.text_frame and title_shape.text_frame.paragraphs:
                                p = title_shape.text_frame.paragraphs[0]
                                if hasattr(p, 'font'):
                                    p.font.name = template_config["font_family"]
                                    p.font.size = Pt(template_config["title_font_size"])
                                    p.font.color.rgb = RGBColor(*template_config["colors"]["title"])
                    except Exception as title_error:
                        logger.warning(f"Failed to set title for slide {i}: {title_error}")
                        # Try to add title as text box
                        try:
                            title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), Inches(9), Inches(1))
                            title_box.text = slide_data["title"]
                        except:
                            pass

                    # Add content
                    if slide_data["content"]:
                        self._add_slide_content(slide, slide_data, template_config)

                    # Add visuals
                    for visual in slide_data["visuals"]:
                        try:
                            if visual["lang"] == "json" and "vega" in visual["code"].lower():
                                img_path = render_vega_lite(visual["code"], self.work_dir)
                                if img_path and img_path.exists():
                                    picture = slide.shapes.add_picture(str(img_path), Inches(3), Inches(2), width=Inches(4))
                                    try:
                                        if slide_data.get("alt_text"):
                                            picture.alt_text = slide_data["alt_text"][0]
                                    except Exception as alt_err:
                                        logger.warning(
                                            f"Failed to set alt text for slide {slide_data['title']}: {alt_err}"
                                        )
                            elif visual["lang"] == "mermaid":
                                # Add placeholder for Mermaid diagrams
                                textbox = slide.shapes.add_textbox(Inches(3), Inches(2), Inches(4), Inches(2))
                                textbox.text = f"Mermaid Diagram:\n{visual['code'][:100]}..."
                                if textbox.text_frame.paragraphs:
                                    p = textbox.text_frame.paragraphs[0]
                                    p.font.name = template_config["font_family"]
                                    p.font.size = Pt(12)
                        except Exception as e:
                            logger.warning(f"Failed to add visual to slide {slide_data['title']}: {e}")
                            
                except Exception as e:
                    logger.error(f"Error creating slide {i}: {e}")
                    continue

            prs.save(str(output_file))
            logger.info(f"Successfully generated PowerPoint: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"PowerPoint generation error: {str(e)}")
            raise ValueError(f"Failed to generate PowerPoint: {str(e)}")

    def _add_slide_content(self, slide, slide_data, template_config):
        """Add content to a slide based on its type"""
        try:
            if not slide_data.get("content"):
                return
                
            if slide_data["type"] == "comparison" and len(slide.placeholders) >= 3:
                # Use two-column layout
                try:
                    left_placeholder = slide.placeholders[1]
                    right_placeholder = slide.placeholders[2]
                    
                    for i, item in enumerate(slide_data["content"]):
                        target = left_placeholder if i % 2 == 0 else right_placeholder
                        if hasattr(target, 'text_frame') and target.text_frame:
                            target.text += f"• {item}\n"
                            try:
                                if target.text_frame.paragraphs:
                                    p = target.text_frame.paragraphs[0]
                                    p.font.name = template_config["font_family"]
                                    p.font.size = Pt(template_config["body_font_size"])
                                    p.font.color.rgb = RGBColor(*template_config["colors"]["body"])
                            except Exception as font_error:
                                logger.warning(f"Font formatting failed: {font_error}")
                except Exception as layout_error:
                    logger.warning(f"Two-column layout failed: {layout_error}")
                    # Fall back to standard layout
                    self._add_standard_content(slide, slide_data, template_config)
            else:
                # Standard content layout
                self._add_standard_content(slide, slide_data, template_config)
        except Exception as e:
            logger.warning(f"Failed to add content to slide: {e}")
    
    def _add_standard_content(self, slide, slide_data, template_config):
        """Add content using standard single-column layout"""
        try:
            content_placeholder = None
            
            # Try different methods to find content placeholder
            # Method 1: Look for body placeholder by type
            try:
                for placeholder in slide.placeholders:
                    if hasattr(placeholder, 'placeholder_format') and placeholder.placeholder_format.type == 2:  # Body placeholder
                        content_placeholder = placeholder
                        break
            except:
                pass
            
            # Method 2: Look for placeholders by index (common patterns)
            if not content_placeholder:
                try:
                    for idx in [1, 2, 3]:  # Common content placeholder indices
                        if idx < len(slide.placeholders):
                            placeholder = slide.placeholders[idx]
                            if (hasattr(placeholder, 'text_frame') and 
                                placeholder.text_frame and 
                                placeholder != slide.shapes.title):
                                content_placeholder = placeholder
                                break
                except:
                    pass
            
            # Method 3: Find any text frame that's not the title
            if not content_placeholder:
                try:
                    for shape in slide.shapes:
                        if (hasattr(shape, 'text_frame') and 
                            shape.text_frame and 
                            shape != slide.shapes.title and
                            hasattr(shape, 'placeholder_format')):
                            content_placeholder = shape
                            break
                except:
                    pass
            
            # Method 4: Create a text box if no placeholder found
            if not content_placeholder:
                try:
                    from python_pptx.util import Inches
                    content_placeholder = slide.shapes.add_textbox(
                        Inches(0.5), Inches(1.5), Inches(9), Inches(5)
                    )
                    logger.info("Created new text box for content")
                except Exception as e:
                    logger.warning(f"Failed to create text box: {e}")
                    return
            
            # Add content if placeholder found or created
            if content_placeholder and hasattr(content_placeholder, 'text_frame') and content_placeholder.text_frame:
                content_text = "\n".join([f"• {item}" for item in slide_data["content"]])
                content_placeholder.text = content_text
                
                try:
                    if content_placeholder.text_frame.paragraphs:
                        for p in content_placeholder.text_frame.paragraphs:
                            if hasattr(p, 'font'):
                                p.font.name = template_config["font_family"]
                                p.font.size = Pt(template_config["body_font_size"])
                                p.font.color.rgb = RGBColor(*template_config["colors"]["body"])
                except Exception as font_error:
                    logger.warning(f"Font formatting failed: {font_error}")
            else:
                logger.warning("No suitable content placeholder found and couldn't create one")
                
        except Exception as e:
            logger.warning(f"Failed to add standard content: {e}")