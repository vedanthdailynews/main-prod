#!/usr/bin/env bash
# Render.com build script — runs once on every deploy
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Collect static files (WhiteNoise will serve them)
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate --no-input

# Fetch initial news so the site has content immediately after deploy.
# Keep this lean — only RSS fetching, no external image API calls.
echo "Fetching initial news from Google News..."
python manage.py fetch_news || echo "News fetch failed (non-fatal) — APScheduler will retry on first request."

echo "Build complete."
