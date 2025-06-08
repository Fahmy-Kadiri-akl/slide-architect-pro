# Slide Architect Pro v3.2

A secure, portable MCP server for generating professional slide decks via a chat interface, with story-driven narratives, accessible visuals, and automation support.

## Installation

```bash
pip install slide-architect-pro
```

## Usage

### Starting the MCP Server

Run the server locally:

```bash
python run_server.py
```

The server exposes:
- **WebSocket**: `ws://localhost:8000/chat` for real-time chat
- **HTTP**: `http://localhost:8000/chat` for API-driven chat

### Chat Interface

Interact via a chatbot (e.g., web app, Slack bot) or API calls.

**WebSocket Example** (JavaScript):

```javascript
const ws = new WebSocket("ws://localhost:8000/chat");
ws.onopen = () => {
    ws.send(JSON.stringify({
        message: "Generate a pitch deck for AI cybersecurity, audience: investors, context: TechCrunch Disrupt, key message: Invest in AI security, template: corporate, include a sequence diagram of login process",
        llm_provider: "offline"
    }));
};
ws.onmessage = (event) => {
    console.log(JSON.parse(event.data));
};
```

**HTTP Example** (cURL):

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Generate a pitch deck for AI cybersecurity with a flowchart, audience: investors", "llm_provider": "offline"}'
```

**Response**:

```json
{
  "id": "uuid",
  "message": "Your slide deck 'AI Cybersecurity Pitch' is ready! Download PowerPoint: /tmp/.../AI_Cybersecurity_Pitch.pptx, Markdown: /tmp/.../AI_Cybersecurity_Pitch.md, JSON: /tmp/.../AI_Cybersecurity_Pitch.json",
  "files": {
    "pptx": "/tmp/.../AI_Cybersecurity_Pitch.pptx",
    "markdown": "/tmp/.../AI_Cybersecurity_Pitch.md",
    "json": "/tmp/.../AI_Cybersecurity_Pitch.json"
  }
}
```

### LLM Integration

For Gemini or ChatGPT:

```bash
export GEMINI_API_KEY=your-gemini-key
export OPENAI_API_KEY=your-openai-key
```

Send a chat message with:

```json
{
  "message": "Generate a pitch deck for AI cybersecurity with a sequence diagram",
  "llm_provider": "gemini",
  "api_key": "$GEMINI_API_KEY"
}
```

## Security Features

- **Input Validation**: Sanitized to prevent injection attacks
- **Safe File Handling**: Isolated directory for files
- **API Security**: HTTPS, timeouts, and optional API key authentication
- **Dependency Security**: Pinned secure versions
- **Code Execution Prevention**: Python code blocks ignored
- **Logging**: Structured logs without sensitive data

## Setup Instructions

1. **Install Dependencies**:
   ```bash
   pip install slide-architect-pro
   ```

2. **Set Environment Variables**:
   ```bash
   export SLIDE_WORK_DIR=/path/to/secure/dir
   export GEMINI_API_KEY=your-gemini-key  # Optional
   export OPENAI_API_KEY=your-openai-key  # Optional
   ```

3. **Run Server**:
   ```bash
   python run_server.py
   ```

4. **Dependency Auditing**:
   ```bash
   pip install safety
   safety check
   ```

## Features

- **Chat-Only Interface**: WebSocket or HTTP API with LLM-based intent extraction
- **Story-Driven**: Hook, Problem, Solution, Conclusion flow
- **Accessible**: WCAG 2.1 compliant
- **Automation-Friendly**: Markdown/JSON outputs
- **LLM-Agnostic**: Gemini, ChatGPT, offline mode
- **Mermaid Diagrams**: LLM-generated configurations for sequence diagrams, flowcharts
- **Rich Layouts**: Title, agenda, comparison, chart, diagram, image-heavy, quote slides
- **Styling Templates**: Minimal, corporate, bold
- **Visual Rendering**: Vega-Lite charts as PNGs
- **Collaboration**: Optional Google Drive, GitHub, Slack

## Requirements

- Python 3.9+
- Dependencies: `python-pptx`, `pydantic`, `aiohttp`, `mistune`, `vega`, `cairosvg`, `bleach`, `fastapi`, `uvicorn`

## SaaS API (Coming Soon)

```bash
curl -X POST https://api.slidearchitect.pro/chat \
  -H "Authorization: Bearer your-api-key" \
  -d '{"message": "Generate a pitch deck for AI cybersecurity"}'
```

## Contributing

Fork on GitHub.

## License

MIT License