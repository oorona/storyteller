#!/usr/bin/env bash
# Launch the character-image Assistant demo, loading the API key
# from ../.env relative to this script.

set -e

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ENV_FILE="$SCRIPT_DIR/../backend/.env"

if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
else
  echo "❌  .env file not found at $ENV_FILE"
  exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
  echo "❌  OPENAI_API_KEY is missing in $ENV_FILE"
  exit 1
fi

source "$SCRIPT_DIR/.venv/bin/activate"

streamlit run "$SCRIPT_DIR/character_image_app.py"
