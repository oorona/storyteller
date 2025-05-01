#!/usr/bin/env bash
# Launch the Assistant-chat Streamlit app, reading OPENAI_API_KEY
# from ../.env (relative to the folder this script lives in).

set -e

# --- Resolve paths ---
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ENV_FILE="$SCRIPT_DIR/../backend/.env"

# --- Load .env one level up ---
if [ -f "$ENV_FILE" ]; then
  # Export everything in the file
  set -a
  source "$ENV_FILE"
  set +a
else
  echo "❌  .env file not found at $ENV_FILE"
  exit 1
fi

# --- Check key present ---
if [ -z "$OPENAI_API_KEY" ]; then
  echo "❌  OPENAI_API_KEY is missing in $ENV_FILE"
  exit 1
fi

# --- Activate venv ---
source "$SCRIPT_DIR/.venv/bin/activate"

# --- Run app ---
streamlit run "$SCRIPT_DIR/chat_assistant_app.py"
