#!/usr/bin/env bash
# Render.com build script — runs once on every deploy
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Collect static files (WhiteNoise will serve them)
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate --no-input

# Fetch initial news so the site has content immediately after deploy
echo "Fetching initial news from Google News..."
python manage.py fetch_news || echo "News fetch failed (non-fatal) — will retry on first request."

# Backfill any articles that still have no image
echo "Backfilling missing images..."
python manage.py fix_empty_images || echo "Image backfill failed (non-fatal)."

# Reprocess Picsum placeholders with topic-relevant images
echo "Reprocessing article images with LoremFlickr topic matching..."
python manage.py reprocess_images --limit 300 || echo "Image reprocessing failed (non-fatal)."

# Classify/re-classify articles that have no category
echo "Categorizing articles..."
python manage.py recategorize_articles || echo "Categorization failed (non-fatal)."
