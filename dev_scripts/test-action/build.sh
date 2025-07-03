#!/usr/bin/env bash
set -e

# 1. Create & activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Upgrade pip & install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Deactivate venv
deactivate

# 4. Package all project files into a zip
ZIP_NAME="mqtt_project_$(date +%Y%m%d_%H%M%S).zip"
zip -r "$ZIP_NAME" .env requirements.txt main.py build.sh

echo "✅ Created $ZIP_NAME containing all project files."
