#!/usr/bin/env bash
# Render.com build script — runs once on every deploy
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Collect static files (WhiteNoise will serve them)
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate --no-input
