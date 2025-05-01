#!/usr/bin/env bash
# ----- CONFIG -----
ENV_DIR=".venv"                 # change if you prefer another path
# ------------------

# Create virtual environment if it doesn’t exist
if [ ! -d "$ENV_DIR" ]; then
  python3 -m venv "$ENV_DIR"
fi

# Activate venv
source "$ENV_DIR/bin/activate"

# Upgrade pip & install deps
pip install --upgrade pip
pip install --upgrade -r requirements.txt

echo "✅ Environment ready. Activate later with: source $ENV_DIR/bin/activate"
