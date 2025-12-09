# Productivity Service

Personal productivity automation suite with AI-powered tools.

## Components

| Component | Description | Docs |
|-----------|-------------|------|
| **Task Capture API** | Voice-to-task with AI parsing for OmniFocus | [Below](#task-capture-api) |
| **Filesystem Daemon** | AI-powered Desktop/Downloads organization | [filesystem-daemon/](filesystem-daemon/README.md) |
| **Obsidian Sync** | Daily note automation | [obsidian-sync/](obsidian-sync/README.md) |
| **Raycast Scripts** | Mac script commands | [raycast/](raycast/README.md) |

## Filesystem Daemon (NEW)

Organize your Desktop and Downloads with AI classification:

```bash
# Interactive organization workflow
uv run python -m filesystem-daemon.cli organize ~/Desktop
```

Features:
- Rule-based + AI classification
- Organizes into life domains (Finance, Health, Work, etc.)
- Standardized file renaming (YYYY-MM-DD-description.ext)
- Interactive review before execution
- Learns from your corrections

See [filesystem-daemon/README.md](filesystem-daemon/README.md) for full documentation.

---

# Task Capture API

Voice-to-task capture with AI tag parsing for OmniFocus.

Captures tasks via:
- **Alexa Skill**: "Alexa, tell Task Capture to add buy milk tomorrow"
- **API**: Direct POST to `/tasks/capture` or `/tasks/parse` + `/tasks/create`
- **Apple Shortcuts**: Chain with Superwhisper for Mac voice input

## Features

- **AI Tag Parsing**: Uses Claude (via Bedrock) to extract project, context, due date from natural language
- **OmniFocus Mail Drop**: Sends formatted emails to create tasks automatically
- **Alexa Integration**: Custom skill for voice task capture
- **Low Latency**: Optimized for < 5 second voice-to-task

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- AWS credentials configured
- Docker (for local Lambda testing)

### Local Development

```bash
# Install dependencies
uv sync

# Run locally with uvicorn
PRODUCTIVITY_DEBUG=true uv run uvicorn src.productivity_service.main:app --reload --port 8000

# Run tests
uv run pytest

# Type checking
uv run mypy src/

# Linting
uv run ruff check .
uv run ruff format .
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/tasks/parse` | Parse natural language → structured task |
| POST | `/tasks/create` | Create task in OmniFocus via Mail Drop |
| POST | `/tasks/capture` | Parse + create in one call |
| POST | `/alexa` | Alexa Skill webhook |

### Example: Parse Task

```bash
curl -X POST http://localhost:8000/tasks/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "Buy milk tomorrow for groceries"}'
```

Response:
```json
{
  "title": "Buy milk",
  "project": "groceries",
  "context": "@errands",
  "due_date": "2024-01-15",
  "defer_date": null,
  "tags": [],
  "confidence": 0.95,
  "raw_input": "Buy milk tomorrow for groceries"
}
```

### Example: Capture Task (Parse + Create)

```bash
curl -X POST http://localhost:8000/tasks/capture \
  -H "Content-Type: application/json" \
  -d '{"text": "Call mom next week"}'
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PRODUCTIVITY_ENVIRONMENT` | Environment name | `development` |
| `PRODUCTIVITY_DEBUG` | Enable debug mode + docs | `false` |
| `PRODUCTIVITY_AWS_REGION` | AWS region | `us-east-1` |
| `PRODUCTIVITY_OMNIFOCUS_MAIL_DROP_ADDRESS` | Your OmniFocus Mail Drop email | (required) |
| `PRODUCTIVITY_SES_SENDER_EMAIL` | Verified SES sender email | (required) |
| `PRODUCTIVITY_BEDROCK_MODEL_ID` | Claude model ID | `anthropic.claude-3-haiku-20240307-v1:0` |

## Deployment

This service deploys automatically to AWS Lambda via GitHub Actions when you push to `main`.

### Initial Setup

1. **Deploy infrastructure** (in `agent-platform` repo):
   - Merge PR to deploy ECR, Lambda, API Gateway

2. **Configure GitHub repository**:

   **Secrets** (Settings → Secrets → Actions):
   - `AWS_ROLE_ARN`: `arn:aws:iam::096908083292:role/github-actions-terraform`

   **Variables** (Settings → Variables → Actions):
   - `AWS_REGION`: `us-east-1`
   - `ECR_REPOSITORY`: `productivity-service`
   - `LAMBDA_FUNCTION_NAME`: `productivity-service`

3. **Initial deployment**:
   ```bash
   ./scripts/initial-deploy.sh
   ```

4. **Configure Lambda environment variables** (AWS Console):
   - `PRODUCTIVITY_OMNIFOCUS_MAIL_DROP_ADDRESS`: Your Mail Drop email
   - `PRODUCTIVITY_SES_SENDER_EMAIL`: Verified SES email

### OmniFocus Mail Drop Setup

1. In OmniFocus, go to Settings → Mail → Get Mail Drop Address
2. Copy your unique `sync-XXXX@sync.omnigroup.com` address
3. Set as `PRODUCTIVITY_OMNIFOCUS_MAIL_DROP_ADDRESS` in Lambda

### SES Setup

1. Verify your sender email in AWS SES
2. If in sandbox mode, also verify your OmniFocus Mail Drop address
3. Set verified email as `PRODUCTIVITY_SES_SENDER_EMAIL` in Lambda

## Alexa Skill Setup

1. Create custom skill in Amazon Developer Console
2. Add `CaptureTaskIntent` with `{taskText}` slot (type: `AMAZON.SearchQuery`)
3. Configure HTTPS endpoint: `<API_GATEWAY_URL>/alexa`
4. Sample utterances:
   - "add {taskText}"
   - "capture {taskText}"
   - "remind me to {taskText}"

## Project Structure

```
productivity-service/
├── src/
│   └── productivity_service/
│       ├── __init__.py
│       ├── main.py              # FastAPI app + Lambda handler
│       ├── config.py            # Settings
│       ├── routes/
│       │   ├── health.py        # GET /health
│       │   ├── tasks.py         # POST /tasks/*
│       │   └── alexa.py         # POST /alexa
│       ├── services/
│       │   ├── tag_parser.py    # AI task parsing (Bedrock)
│       │   ├── omnifocus.py     # Mail Drop integration (SES)
│       │   └── alexa_handler.py # Alexa request handling
│       └── models/
│           ├── task.py          # Task request/response models
│           └── alexa.py         # Alexa models
├── tests/
├── scripts/
│   └── initial-deploy.sh
├── Dockerfile
├── pyproject.toml
└── README.md
```

## License

Proprietary - Marc Knight
