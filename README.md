# AI Personalized Children's Story Generator

This app generates personalized, multi-page children's stories with illustrations.

It now supports two AI providers:
- OpenAI
- Google Gemini (including Gemini image models such as `gemini-2.5-flash-image`, often called Nano Banana)

Default provider is Gemini.

## What Changed

- Added a provider abstraction layer in the backend (`openai` vs `gemini`)
- Added Gemini text + image support for all current generation stages
- Added runtime AI settings in the frontend
- Added provider/model/temperature/image controls on the front page
- Added PDF export: download generated book pages as a PDF file
- Added single-input child profile extraction (structured output) for Step 1
- Added Docker-secrets-compatible key loading from `/run/secrets/...`
- Added settings options endpoint: `GET /api/settings/options`

## Project Structure

```text
storyteller/
├── backend/
│   ├── app.py
│   ├── provider_service.py
│   ├── openai_service.py
│   ├── gemini_service.py
│   ├── secret_utils.py
│   ├── .env
│   ├── requirements.txt
│   └── prompts/
│   └── schemas/
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── secrets/
│   ├── .gitkeep
│   ├── openai_api_key.example
│   └── gemini_api_key.example
├── Dockerfile
├── docker-compose.yaml
└── README.md
```

## AI Settings in UI

On Step 1, there is now an **AI Settings** section.

You can configure:
- Provider (`OpenAI` or `Google Gemini`)
- Text model
- Text temperature
- Image model (generate)
- Image model (edit)
- OpenAI image settings (size, quality, output format)
- Gemini image settings (aspect ratio, resolution)

These settings are sent with every API request.

Step 1 now uses one free-text field (about the child) and extracts:
- child name
- learning goal
- interests/personality keywords
- story theme suggestions
- character suggestions

Prompt and schema are editable files:
- `backend/prompts/child_profile_extraction_prompt.txt`
- `backend/schemas/child_profile_extraction_schema.json`

Each extraction call is also persisted to:
- `backend/generated/profile_extractions/`

## Secrets (Required)

Create local secret files:

```bash
mkdir -p secrets
printf 'YOUR_OPENAI_KEY' > secrets/openai_api_key
printf 'YOUR_GEMINI_KEY' > secrets/gemini_api_key
```

Do not add quotes or trailing spaces.
Use only the key value in those files (no `#` comments in the key line).

`docker-compose.yaml` mounts these as Docker secrets:
- `/run/secrets/openai_api_key`
- `/run/secrets/gemini_api_key`

The backend reads keys in this order:
1. Direct env var (`OPENAI_API_KEY` / `GEMINI_API_KEY`)
2. File env var (`OPENAI_API_KEY_FILE` / `GEMINI_API_KEY_FILE`)
3. Default Docker secret file path

## Local Run (without Docker)

1. Install dependencies:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Provide key files and point `.env` to them, for example:

```dotenv
OPENAI_API_KEY_FILE=../secrets/openai_api_key
GEMINI_API_KEY_FILE=../secrets/gemini_api_key
```

3. Run backend:

```bash
python app.py
```

4. Open:
- `http://localhost:5001`

## Docker Run

From repo root:

1. Create a root `.env` (next to `docker-compose.yaml`) and define the Traefik domain:

```dotenv
TRAEFIK_DOMAIN=storyteller.home.iktdts.com
```

2. Start the stack:

```bash
docker compose up --build
```

Then open:
- `http://localhost:5001`

## API Endpoints

- `GET /api/health`
- `GET /api/settings/options`
- `POST /api/characters/suggest`
- `POST /api/profile/extract`
- `POST /api/names/suggest`
- `POST /api/plot/suggest`
- `POST /api/image/generate`
- `POST /api/book/generate`
- `POST /api/book/pdf`

All POST endpoints accept optional provider context:

```json
{
  "provider": "openai",
  "settings": {
    "text_model": "gpt-4.1-mini",
    "text_temperature": 0.7,
    "image_model": "gpt-image-1",
    "image_edit_model": "gpt-image-1"
  }
}
```

## Notes

- Book generation still runs per-section image creation in parallel threads.
- Different providers/models may produce different style and quality.
- API usage cost depends on model choice and story length.
