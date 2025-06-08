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
from pathlib import Path
import uuid
import re
import logging
from .llm_adapters import LLMAdapter
from .templates import SLIDE_ARCHITECT_PROMPT_V3_2
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
        self.prompt = SLIDE_ARCHITECT_PROMPT_V3 + "\n\n### Additional Instructions\n- For diagram requests (e.g., sequence diagram, flowchart), generate a valid Mermaid code block tailored to the slide's context. Ensure the diagram is concise (≤10 nodes) and includes a descriptive alt text."
        self.work_dir = Path(os.getenv("SLIDE_WORK_DIR", f"/tmp/slide_architect_pro_{uuid.uuid4()}"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.templates = {
            "minimal": {
                "font": "Arial",
                "title_size": Pt(24),
                "body_size": Pt(18),
                "colors": {"title": (0, 0, 0), "body": (0, 0, 0), "background": (255, 255, 255)},
                "logo_pos": (Inches(0.5), Inches(0.5))
            },
            "corporate": {
                "font": "Calibri",
                "title_size": Pt(28),
                "body_size": Pt(20),
                "colors": {"title": (0, 51, 102), "body": (51, 51, 51), "background": (240, 240, 240)},
                "logo_pos": (Inches(0.3), Inches(0.3))
            },
            "bold": {
                "font": "Arial",
                "title_size": Pt(32),
                "body_size": Pt(22),
                "colors": {"title": (200, 0, 0), "body": (0, 0, 0), "background": (255, 255, 200)},
                "logo_pos": (Inches(0.5), Inches(0.5))
            }
        }

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
                markdown_output = self._offline_response(full_prompt)
            else:
                markdown_output = await llm_adapter.generate(full_prompt)
                if len(markdown_output) > 100_000:
                    logger.warning("LLM response too large")
                    raise ValueError("LLM response exceeds maximum size")
                markdown_output = bleach.clean(markdown_output, tags=["pre", "code"], strip=True)

            json_output = self._convert_markdown_to_json(markdown_output)
            self._validate_automation_edge_cases(json_output)

            pptx_file = self._generate_pptx(json_output, input_data.topic, input_data.template)

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
{
  "topic": "AI Cybersecurity Pitch",
  "audience": "Investors",
  "context": "TechCrunch Disrupt",
  "key_message": "Invest in AI security",
  "tone": "Formal",
  "style": "Clean & minimal",
  "template": "corporate"
}
```
"""
            intent_output = await llm_adapter.generate(intent_prompt)
            if len(intent_output) > 10_000:
                logger.warning("Intent extraction response too large")
                return self._regex_parse_chat_message(message)

            try:
                intent_data = json.loads(intent_output.strip("```json\n").strip("```"))
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

    def _offline_response(self, prompt: str) -> str:
        return """# Slide 1 - Title Slide  
**Title:** {topic}  
**Subtitle:** {context}  
**Logo:** Top-right corner  
**Slide Notes:** Introduce the topic.  
**Engagement Techniques:** Share an anecdote.

# Slide 2 - Agenda  
**Title:** Agenda  
- Hook  
- Problem  
- Solution  
- Conclusion  

# Slide 3 - Hook  
**Title:** Why This Matters  
**Body:**  
- Engaging statistic or story  
**Visual:** Vega-Lite chart  
```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "data": {"values": [{"x": "A", "y": 10}, {"x": "B", "y": 20}]},
  "mark": "bar",
  "encoding": {"x": {"field": "x"}, "y": {"field": "y"}}
}
```  
**Alt Text:** Bar chart showing key data.  
**Slide Notes:** Set the stage.  
**Engagement Techniques:** Ask a question.

# Slide 4 - Solution  
**Title:** Our Solution  
**Body:**  
- Key feature 1  
- Key feature 2  
**Visual:** Mermaid diagram  
```mermaid
sequenceDiagram
  User->>System: Request
  System-->>User: Response
```  
**Alt Text:** Diagram of process flow.  
**Slide Notes:** Highlight benefits.

# Slide 5 - Closing  
**Title:** Call to Action  
**Body:**  
- {key_message}  
**Slide Notes:** Summarize and close.  
**Engagement Techniques:** Invite questions.
""".format(topic=input_data.topic, context=input_data.context, key_message=input_data.key_message)

    def _convert_markdown_to_json(self, markdown_text: str) -> Dict:
        try:
            parser = mistune.create_markdown(renderer=SlideRenderer())
            slides = parser(markdown_text)
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
                for visual in slide["visuals"]:
                    if visual["lang"] == "json" and "vega" in visual["code"].lower():
                        try:
                            data = json.loads(visual["code"])["data"]["values"]
                            if len(data) > 50:
                                logger.warning(f"Chart dataset exceeds 50 points in slide {slide['title']}")
                                raise ValueError("Chart dataset exceeds 50 data points")
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid Vega-Lite JSON in slide {slide['title']}")
                            slide["visuals"].remove(visual)
                    elif visual["lang"] in ["mermaid", "plantuml"]:
                        nodes = visual["code"].count("->")
                        if nodes > 10:
                            logger.warning(f"Mermaid/PlantUML diagram too complex in slide {slide['title']}")
                            slide["notes"].append("Consider splitting complex diagram across multiple slides")
                    elif visual["lang"] == "python":
                        logger.warning(f"Python code block ignored in slide {slide['title']}")
                        slide["visuals"].remove(visual)
            except Exception as e:
                logger.error(f"Validation error in slide {slide['title']}: {str(e)}")
                slide["notes"].append(f"Validation error: {str(e)}")

    def _generate_pptx(self, json_data: Dict, title: str, template: str) -> Path:
        try:
            prs = Presentation()
            template = self.templates.get(template, self.templates["minimal"])
            output_file = self.work_dir / f"{title.replace(' ', '_')}.pptx"

            for i, slide_data in enumerate(json_data["slides"]):
                if i == 0:
                    layout = prs.slide_layouts[0]
                elif slide_data["type"] == "chart":
                    layout = prs.slide_layouts[6]
                elif slide_data["type"] == "diagram":
                    layout = prs.slide_layouts[6]
                elif "comparison" in slide_data["title"].lower():
                    layout = prs.slide_layouts[3]
                elif slide_data["visuals"] and not slide_data["content"]:
                    layout = prs.slide_layouts[8]
                elif "quote" in slide_data["title"].lower():
                    layout = prs.slide_layouts[5]
                else:
                    layout = prs.slide_layouts[1]

                slide = prs.slides.add_slide(layout)
                title_shape = slide.shapes.title
                if title_shape:
                    title_shape.text = slide_data["title"]
                    title_shape.text_frame.paragraphs[0].font.name = template["font"]
                    title_shape.text_frame.paragraphs[0].font.size = template["title_size"]

                if slide_data["content"]:
                    if slide_data["type"] == "comparison":
                        left = slide.placeholders[1]
                        right = slide.placeholders[2]
                        for i, item in enumerate(slide_data["content"]):
                            (left if i % 2 == 0 else right).text += item + "\n"
                            (left if i % 2 == 0 else right).text_frame.paragraphs[0].font.name = template["font"]
                            (left if i % 2 == 0 else right).text_frame.paragraphs[0].font.size = template["body_size"]
                    elif slide_data["type"] == "quote":
                        textbox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(4))
                        textbox.text = "\n".join(slide_data["content"])
                        textbox.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
                        textbox.text_frame.paragraphs[0].font.name = template["font"]
                        textbox.text_frame.paragraphs[0].font.size = Pt(24)
                    else:
                        body_shape = slide.placeholders[1] if 1 in slide.placeholders else None
                        if body_shape:
                            body_shape.text = "\n".join(slide_data["content"])
                            body_shape.text_frame.paragraphs[0].font.name = template["font"]
                            body_shape.text_frame.paragraphs[0].font.size = template["body_size"]

                for visual in slide_data["visuals"]:
                    if visual["lang"] == "json" and "vega" in visual["code"].lower():
                        try:
                            img_path = render_vega_lite(visual["code"], self.work_dir)
                            slide.shapes.add_picture(str(img_path), Inches(3), Inches(2), width=Inches(4))
                        except Exception as e:
                            logger.warning(f"Failed to render Vega-Lite in slide {slide_data['title']}: {str(e)}")
                    elif visual["lang"] == "mermaid":
                        slide.shapes.add_textbox(Inches(3), Inches(2), Inches(4), Inches(2)).text = "Mermaid Diagram Placeholder"

            prs.save(str(output_file))
            return output_file
        except Exception as e:
            logger.error(f"PowerPoint generation error: {str(e)}")
            raise ValueError(f"Failed to generate PowerPoint: {str(e)}")