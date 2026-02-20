# Vedant Daily News

A modern news aggregation platform that fetches and displays news from Google News, categorized by continent and enhanced with AI-powered analysis.

## Features

- 🌍 **Multi-Continent Coverage**: News organized by continents (Africa, Asia, Europe, North America, South America, Oceania)
- ⏱️ **Real-time Updates**: Automatically fetches latest news every 2 minutes
- 🤖 **AI-Powered**: AI-generated summaries, sentiment analysis, and smart tagging
- 📱 **Responsive Design**: Beautiful, mobile-friendly interface
- 🔍 **Advanced Search**: Filter by continent, category, and keywords
- 📊 **REST API**: Full-featured API for integration with other applications
- ⭐ **Featured Stories**: Curated and trending news sections

## Technology Stack

- **Backend**: Python 3.10+, Django 5.0+
- **Task Queue**: Celery with Redis
- **Database**: SQLite (development) / PostgreSQL (production)
- **AI**: OpenAI GPT-3.5 or Anthropic Claude
- **Frontend**: Bootstrap 5, Font Awesome
- **API**: Django REST Framework

## Project Structure

```
Vedant Daily News Project/
├── vedant_news/           # Django project settings
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── news/                  # News application
│   ├── models.py         # Database models
│   ├── views.py          # Views and viewsets
│   ├── serializers.py    # REST API serializers
│   ├── services.py       # Google News service
│   ├── ai_service.py     # AI processing service
│   ├── tasks.py          # Celery tasks
│   ├── admin.py          # Django admin configuration
│   └── urls.py           # URL routing
├── templates/            # HTML templates
│   ├── base.html
│   └── news/
│       ├── home.html
│       ├── detail.html
│       ├── continent.html
│       └── category.html
├── static/               # Static files (CSS, JS, images)
├── celeryapp.py         # Celery configuration
├── manage.py            # Django management script
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
└── README.md            # This file
```

## Installation

### Prerequisites

- Python 3.10 or higher
- Redis server
- Virtual environment (recommended)

### Setup Steps

1. **Clone or navigate to the project directory**

2. **Create and activate virtual environment** (if not already created):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   # source .venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   copy .env.example .env  # On Windows
   # cp .env.example .env  # On macOS/Linux
   ```
   
   Edit `.env` and configure:
   - `SECRET_KEY`: Django secret key
   - `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`: For AI features (optional)
   - `REDIS_URL`: Redis connection URL
   - Other settings as needed

5. **Run migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create superuser** (for admin access):
   ```bash
   python manage.py createsuperuser
   ```

7. **Collect static files**:
   ```bash
   python manage.py collectstatic --noinput
   ```

## Running the Application

### Method 1: Development Server Only

For testing without background tasks:

```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000

### Method 2: Full Setup with Celery (Recommended)

You need to run three separate terminals:

**Terminal 1 - Redis Server**:
```bash
redis-server
```

**Terminal 2 - Django Development Server**:
```bash
python manage.py runserver
```

**Terminal 3 - Celery Worker**:
```bash
celery -A celeryapp worker --loglevel=info --pool=solo
```

**Terminal 4 - Celery Beat (for scheduled tasks)**:
```bash
celery -A celeryapp beat --loglevel=info
```

### Accessing the Application

- **Frontend**: http://127.0.0.1:8000/
- **Admin Panel**: http://127.0.0.1:8000/admin/
- **API Root**: http://127.0.0.1:8000/api/
- **API Articles**: http://127.0.0.1:8000/api/articles/
- **API Sources**: http://127.0.0.1:8000/api/sources/

## API Endpoints

### News Articles

- `GET /api/articles/` - List all articles
- `GET /api/articles/{id}/` - Get article details
- `GET /api/articles/by_continent/?continent=AS` - Filter by continent
- `GET /api/articles/featured/` - Get featured articles
- `GET /api/articles/trending/` - Get trending articles
- `POST /api/articles/fetch_news/` - Trigger manual news fetch
- `POST /api/articles/{id}/process_with_ai/` - Process article with AI

### News Sources

- `GET /api/sources/` - List all news sources
- `GET /api/sources/{id}/` - Get source details

### Query Parameters

- `continent`: Filter by continent (AF, AS, EU, NA, SA, OC, GL)
- `category`: Filter by category (WORLD, BUSINESS, TECHNOLOGY, etc.)
- `is_featured`: Filter featured articles (true/false)
- `sentiment`: Filter by sentiment (positive/negative/neutral)
- `search`: Search in title, description, source
- `ordering`: Sort by field (published_at, view_count, created_at)

## Configuration

### News Polling Interval

The default polling interval is 2 minutes (120 seconds). To change:

1. Edit `.env`:
   ```
   NEWS_POLL_INTERVAL=120  # seconds
   ```

2. Or modify `celeryapp.py`:
   ```python
   app.conf.beat_schedule = {
       'fetch-news-every-2-minutes': {
           'task': 'news.tasks.fetch_all_news',
           'schedule': 120.0,  # seconds
       },
   }
   ```

### AI Configuration

The application supports both OpenAI and Anthropic:

1. **OpenAI** (GPT-3.5):
   ```
   OPENAI_API_KEY=sk-...
   ```

2. **Anthropic** (Claude):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

AI features include:
- Article summarization
- Sentiment analysis (positive/negative/neutral)
- Automatic tag generation

### Database Configuration

**Development** (SQLite - default):
```python
# Already configured in settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

**Production** (PostgreSQL):
```env
DATABASE_URL=postgresql://user:password@localhost:5432/vedant_news
```

## Management Commands

### Manual News Fetch

Fetch news immediately without waiting for scheduled task:

```bash
python manage.py shell
>>> from news.tasks import fetch_all_news
>>> fetch_all_news()
```

### Clean Old News

Remove articles older than 7 days:

```bash
python manage.py shell
>>> from news.tasks import cleanup_old_news
>>> cleanup_old_news()
```

### Process Articles with AI

```bash
python manage.py shell
>>> from news.tasks import batch_process_articles
>>> batch_process_articles(limit=10)
```

## Customization

### Add Custom News Categories

Edit `news/models.py`:

```python
class Category(models.TextChoices):
    WORLD = 'WORLD', 'World'
    BUSINESS = 'BUSINESS', 'Business'
    YOUR_CATEGORY = 'YOUR_CATEGORY', 'Your Category Name'
    # Add more categories
```

### Modify Featured Articles Logic

Edit `news/views.py` - `HomePageView.get_context_data()` method.

### Change Theme/Styling

Edit `templates/base.html` or add custom CSS files to `static/css/`.

## Troubleshooting

### News not fetching automatically

1. Ensure Redis is running
2. Check Celery worker is running
3. Check Celery beat scheduler is running
4. Verify logs for errors

### AI features not working

1. Verify API keys in `.env`
2. Check internet connectivity
3. Review AI service logs

### Database errors

```bash
python manage.py migrate --run-syncdb
```

### Static files not loading

```bash
python manage.py collectstatic --clear --noinput
```

## Production Deployment

### Security Checklist

- [ ] Set `DEBUG=False` in `.env`
- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set up HTTPS
- [ ] Configure proper CORS settings
- [ ] Set up proper logging
- [ ] Use environment variables for all secrets

### Recommended Stack

- **Web Server**: Gunicorn + Nginx
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Process Manager**: Supervisor or systemd
- **Platform**: AWS, DigitalOcean, Heroku, etc.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is created for educational purposes.

## Support

For issues and questions, please open an issue on the project repository.

---

**Vedant Daily News** - Keeping you informed, powered by AI 🌍📰
