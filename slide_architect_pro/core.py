# slide_architect_pro/core.py

import asyncio
from pydantic import BaseModel, validator
from typing import Optional, Dict, List
import json
import os
import mistune
import bleach
from python_pptx import Presentation
from python_pptx.util import Inches, Pt
from python_pptx.enum.text import PP_ALIGN
from python_pptx.dml.color import RGBColor
from pathlib import Path
import uuid
import re
import logging
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

    @validator("*")
    def sanitize_input(cls, v):
        if isinstance(v, str):
            cleaned = bleach.clean(v, tags=[], strip=True)
            if not re.match(r'^[\w\s\-\&\#\$\%\(\)\[\]\{\}\.\,\!\?\:\;\"\'\/]*$', cleaned):
                logger.warning(f"Invalid characters in input: {v}")
                raise ValueError(f"Invalid characters in input: {cleaned}")
            return cleaned
        return v

class SlideRenderer(mistune.HTMLRenderer):
    def __init__(self):
        super().__init__()
        self.slides = []
        self.current_slide = None
        self.section = None

    def heading(self, text, level, **attrs):
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

    def paragraph(self, text):
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

    def list_item(self, text):
        text = bleach.clean(text, tags=[], strip=True)
        if self.section == "content":
            self.current_slide["content"].append(text.strip())
        return ""

    def block_code(self, code, info=None):
        if self.section == "visuals":
            if info in ["json", "mermaid", "plantuml", "latex"]:
                code = bleach.clean(code, tags=[], strip=True)
                if info == "mermaid" and len(code.split("\n")) > 20:
                    logger.warning("Mermaid diagram too complex")
                    return ""
                self.current_slide["visuals"].append({"code": code, "lang": info or "text"})
            else:
                logger.warning(f"Unsupported code block language: {info}")
        return ""

    def finish(self):
        if self.current_slide:
            self.slides.append(self.current_slide)
        return self.slides

class SlideArchitectPro:
    def __init__(self):
        self.prompt = SLIDE_ARCHITECT_PROMPT_V3_2 + "\n\n### Additional Instructions\n- For diagram requests (e.g., sequence diagram, flowchart), generate a valid Mermaid code block tailored to the slide's context. Ensure the diagram is concise (≤10 nodes) and includes a descriptive alt text."
        self.work_dir = Path(os.getenv("SLIDE_WORK_DIR", f"/tmp/slide_architect_pro_{uuid.uuid4()}"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.templates = TEMPLATE_CONFIGS

    async def generate_deck(self, input_data: SlideInput, llm_adapter: LLMAdapter) -> Dict:
        try:
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

            if isinstance(llm_adapter, str) and llm_adapter == "offline":
                markdown_output = self._offline_response(full_prompt, input_data)
            else:
                markdown_output = await llm_adapter.generate(full_prompt)
                if len(markdown_output) > 100_000:
                    logger.warning("LLM response too large")
                    raise ValueError("LLM response exceeds maximum size")
                markdown_output = bleach.clean(markdown_output, tags=["pre", "code"], strip=True)

            json_output = self._convert_markdown_to_json(markdown_output)
            self._validate_automation_edge_cases(json_output)

            pptx_file = await self._generate_pptx(json_output, input_data.topic, input_data.template)

            md_file = self.work_dir / f"{input_data.topic.replace(' ', '_')}.md"
            json_file = self.work_dir / f"{input_data.topic.replace(' ', '_')}.json"
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

    async def parse_chat_message(self, message: str, llm_adapter: LLMAdapter) -> SlideInput:
        try:
            message = bleach.clean(message, tags=[], strip=True)
            if isinstance(llm_adapter, str) and llm_adapter == "offline":
                return self._regex_parse_chat_message(message)

            intent_prompt = f"""
Parse the following chat message into a JSON object with fields: topic, audience, context, key_message, tone, style, template.
If a field is not specified, use default values: topic="Untitled Presentation", audience="General", context="Business presentation", key_message="Take action", tone=None, style=None, template="minimal".
Ensure the output is valid JSON.

Message: {message}

Example Output:
```json
{{
  "topic": "AI Cybersecurity Pitch",
  "audience": "Investors",
  "context": "TechCrunch Disrupt",
  "key_message": "Invest in AI security",
  "tone": "Formal",
  "style": "Clean & minimal",
  "template": "corporate"
}}
```
"""
            intent_output = await llm_adapter.generate(intent_prompt)
            if len(intent_output) > 10_000:
                logger.warning("Intent extraction response too large")
                return self._regex_parse_chat_message(message)

            try:
                # Extract JSON from response
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', intent_output, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = intent_output.strip("```json\n").strip("```")
                
                intent_data = json.loads(json_str)
                return SlideInput(**intent_data)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from intent extraction")
                return self._regex_parse_chat_message(message)
        except Exception as e:
            logger.error(f"Error parsing chat message: {str(e)}")
            return self._regex_parse_chat_message(message)

    def _regex_parse_chat_message(self, message: str) -> SlideInput:
        message = bleach.clean(message, tags=[], strip=True)
        topic = "Untitled Presentation"
        audience = "General"
        context = "Business presentation"
        key_message = "Take action"
        template = "minimal"

        if "for" in message.lower():
            topic_match = re.search(r"generate.*?(?:for|about)\s+([^\,]+)", message, re.I)
            if topic_match:
                topic = topic_match.group(1).strip()
        if "audience" in message.lower():
            audience_match = re.search(r"audience\s*:\s*([^\,]+)", message, re.I)
            if audience_match:
                audience = audience_match.group(1).strip()
        if "context" in message.lower():
            context_match = re.search(r"context\s*:\s*([^\,]+)", message, re.I)
            if context_match:
                context = context_match.group(1).strip()
        if "key message" in message.lower() or "cta" in message.lower():
            key_message_match = re.search(r"(?:key message|cta)\s*:\s*([^\,]+)", message, re.I)
            if key_message_match:
                key_message = key_message_match.group(1).strip()
        if "template" in message.lower():
            template_match = re.search(r"template\s*:\s*([^\,]+)", message, re.I)
            if template_match:
                template = template_match.group(1).strip()

        return SlideInput(
            topic=topic,
            audience=audience,
            context=context,
            key_message=key_message,
            template=template
        )

    def _offline_response(self, prompt: str, input_data: SlideInput) -> str:
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

    def _convert_markdown_to_json(self, markdown_text: str) -> Dict:
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

    def _validate_automation_edge_cases(self, json_data: Dict):
        for slide in json_data["slides"]:
            try:
                visuals_to_remove = []
                for i, visual in enumerate(slide["visuals"]):
                    if visual["lang"] == "json" and "vega" in visual["code"].lower():
                        try:
                            data = json.loads(visual["code"])["data"]["values"]
                            if len(data) > 50:
                                logger.warning(f"Chart dataset exceeds 50 points in slide {slide['title']}")
                                visuals_to_remove.append(i)
                        except (json.JSONDecodeError, KeyError):
                            logger.warning(f"Invalid Vega-Lite JSON in slide {slide['title']}")
                            visuals_to_remove.append(i)
                    elif visual["lang"] in ["mermaid", "plantuml"]:
                        nodes = visual["code"].count("->") + visual["code"].count("-->>")
                        if nodes > 10:
                            logger.warning(f"Mermaid/PlantUML diagram too complex in slide {slide['title']}")
                            slide["notes"].append("Consider splitting complex diagram across multiple slides")
                    elif visual["lang"] == "python":
                        logger.warning(f"Python code block ignored in slide {slide['title']}")
                        visuals_to_remove.append(i)
                
                # Remove invalid visuals (in reverse order to maintain indices)
                for i in reversed(visuals_to_remove):
                    slide["visuals"].pop(i)
                    
            except Exception as e:
                logger.error(f"Validation error in slide {slide['title']}: {str(e)}")
                slide["notes"].append(f"Validation error: {str(e)}")

    async def _generate_pptx(self, json_data: Dict, title: str, template: str) -> Path:
        try:
            # Try to download template if it's a downloadable one
            template_file = download_template(template, self.work_dir)
            
            if template_file and template_file.exists():
                logger.info(f"Using downloaded template: {template_file}")
                prs = Presentation(str(template_file))
            else:
                logger.info("Using default presentation template")
                prs = Presentation()
            
            template_config = get_template_config(template)
            output_file = self.work_dir / f"{title.replace(' ', '_')}.pptx"

            for i, slide_data in enumerate(json_data["slides"]):
                # Choose layout based on slide type and content
                if i == 0:
                    layout = prs.slide_layouts[template_config["layout_preferences"]["title_slide"]]
                elif slide_data["type"] == "chart":
                    layout = prs.slide_layouts[template_config["layout_preferences"]["blank"]]
                elif slide_data["type"] == "diagram":
                    layout = prs.slide_layouts[template_config["layout_preferences"]["blank"]]
                elif "comparison" in slide_data["title"].lower():
                    layout = prs.slide_layouts[template_config["layout_preferences"]["two_column"]]
                elif slide_data["visuals"] and not slide_data["content"]:
                    layout = prs.slide_layouts[template_config["layout_preferences"]["blank"]]
                else:
                    layout = prs.slide_layouts[template_config["layout_preferences"]["content_slide"]]

                slide = prs.slides.add_slide(layout)
                
                # Set title
                if slide.shapes.title:
                    title_shape = slide.shapes.title
                    title_shape.text = slide_data["title"]
                    if title_shape.text_frame.paragraphs:
                        p = title_shape.text_frame.paragraphs[0]
                        p.font.name = template_config["font_family"]
                        p.font.size = Pt(template_config["title_font_size"])
                        p.font.color.rgb = RGBColor(*template_config["colors"]["title"])

                # Add content
                if slide_data["content"]:
                    if slide_data["type"] == "comparison" and len(slide.placeholders) >= 3:
                        # Use two-column layout
                        left_placeholder = slide.placeholders[1]
                        right_placeholder = slide.placeholders[2]
                        
                        for i, item in enumerate(slide_data["content"]):
                            target = left_placeholder if i % 2 == 0 else right_placeholder
                            if target.text_frame:
                                target.text += f"• {item}\n"
                                if target.text_frame.paragraphs:
                                    p = target.text_frame.paragraphs[0]
                                    p.font.name = template_config["font_family"]
                                    p.font.size = Pt(template_config["body_font_size"])
                                    p.font.color.rgb = RGBColor(*template_config["colors"]["body"])
                    else:
                        # Standard content layout
                        content_placeholder = None
                        for placeholder in slide.placeholders:
                            if placeholder.placeholder_format.type == 2:  # Body placeholder
                                content_placeholder = placeholder
                                break
                        
                        if content_placeholder and content_placeholder.text_frame:
                            content_text = "\n".join([f"• {item}" for item in slide_data["content"]])
                            content_placeholder.text = content_text
                            if content_placeholder.text_frame.paragraphs:
                                for p in content_placeholder.text_frame.paragraphs:
                                    p.font.name = template_config["font_family"]
                                    p.font.size = Pt(template_config["body_font_size"])
                                    p.font.color.rgb = RGBColor(*template_config["colors"]["body"])

                # Add visuals
                for visual in slide_data["visuals"]:
                    if visual["lang"] == "json" and "vega" in visual["code"].lower():
                        try:
                            img_path = render_vega_lite(visual["code"], self.work_dir)
                            slide.shapes.add_picture(str(img_path), Inches(3), Inches(2), width=Inches(4))
                        except Exception as e:
                            logger.warning(f"Failed to render Vega-Lite in slide {slide_data['title']}: {str(e)}")
                    elif visual["lang"] == "mermaid":
                        # Add placeholder for Mermaid diagrams
                        textbox = slide.shapes.add_textbox(Inches(3), Inches(2), Inches(4), Inches(2))
                        textbox.text = f"Mermaid Diagram:\n{visual['code'][:100]}..."
                        if textbox.text_frame.paragraphs:
                            p = textbox.text_frame.paragraphs[0]
                            p.font.name = template_config["font_family"]
                            p.font.size = Pt(12)

            prs.save(str(output_file))
            logger.info(f"Successfully generated PowerPoint: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"PowerPoint generation error: {str(e)}")
            raise ValueError(f"Failed to generate PowerPoint: {str(e)}")