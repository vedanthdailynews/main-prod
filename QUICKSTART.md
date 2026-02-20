# Quick Start Guide

## Initial Setup (5 minutes)

### 1. Copy environment file
```bash
copy .env.example .env
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run migrations
```bash
python manage.py migrate
```

### 4. Create admin user
```bash
python manage.py createsuperuser
```

## Running the Application

### Quick Test (Without Celery)
```bash
python manage.py runserver
```
Visit: http://127.0.0.1:8000

⚠️ Note: News won't auto-refresh without Celery

### Full Setup (With Auto-Refresh)

**Step 1** - Start Redis:
```bash
redis-server
```

**Step 2** - Start Django (new terminal):
```bash
python manage.py runserver
```

**Step 3** - Start Celery Worker (new terminal):
```bash
celery -A celeryapp worker --loglevel=info --pool=solo
```

**Step 4** - Start Celery Beat (new terminal):
```bash
celery -A celeryapp beat --loglevel=info
```

## First Time Usage

1. Visit http://127.0.0.1:8000/admin
2. Login with superuser credentials
3. Manually trigger news fetch (or wait 2 minutes)
4. Browse articles at http://127.0.0.1:8000

## Testing API

### Get all articles
```bash
curl http://127.0.0.1:8000/api/articles/
```

### Manually fetch news
```bash
curl -X POST http://127.0.0.1:8000/api/articles/fetch_news/
```

### Filter by continent
```bash
curl http://127.0.0.1:8000/api/articles/by_continent/?continent=AS
```

## Common Issues

**No news showing?**
- Wait 2 minutes for auto-fetch
- Or manually trigger from API
- Check Celery worker is running

**Celery not working?**
- Ensure Redis is running
- Check Windows users use `--pool=solo`

**Static files not loading?**
```bash
python manage.py collectstatic --noinput
```

## What's Next?

1. Configure AI keys in `.env` for smart features
2. Customize categories in `news/models.py`
3. Modify templates in `templates/news/`
4. Add more news sources

---

For detailed documentation, see [README.md](README.md)
