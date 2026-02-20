# Vedant Daily News Project - Copilot Instructions

## Project Overview
Vedant is a daily English newspaper web application similar to Times of India that aggregates news from Google News. The project is fully functional and running.

## ✅ Completed Setup

### Infrastructure
- ✅ Django 5.2+ project scaffolded
- ✅ Virtual environment configured (Python 3.14)
- ✅ Database migrated (SQLite)
- ✅ All dependencies installed
- ✅ Development server running at http://127.0.0.1:8000

### Features Implemented
- ✅ News models (NewsArticle, NewsSource)
- ✅ Google News RSS feed integration
- ✅ Multi-continent support (Africa, Asia, Europe, NA, SA, Oceania, Global)
- ✅ Category-based organization (World, Business, Technology, Entertainment, Sports, Science, Health)
- ✅ Celery task queue setup
- ✅ AI service integration (OpenAI/Anthropic)
- ✅ REST API with Django REST Framework
- ✅ Responsive Bootstrap 5 UI
- ✅ Admin panel configured
- ✅ Auto-refresh every 2 minutes (via Celery)

## Key Features
- Polls Google News every 2 minutes for latest news
- Categorizes news by continent and category
- AI-powered summaries and sentiment analysis
- RESTful API with filtering and search
- Responsive, mobile-friendly interface
- View tracking and featured articles
- Trending news section

## Technology Stack
- Python 3.14.2
- Django 5.2.10
- Celery 5.3+ for task scheduling
- Redis as message broker
- SQLite database (production-ready for PostgreSQL)
- Google News RSS feeds
- AI integration (OpenAI GPT-3.5 / Anthropic Claude)
- Django REST Framework
- Bootstrap 5 + Font Awesome

## Project Structure
```
vedant_news/           # Django project settings
news/                  # News application
  ├── models.py       # NewsArticle, NewsSource models
  ├── views.py        # Template views & API viewsets
  ├── serializers.py  # REST API serializers
  ├── services.py     # Google News fetching service
  ├── ai_service.py   # AI processing (summaries, sentiment)
  ├── tasks.py        # Celery background tasks
  ├── admin.py        # Django admin configuration
  └── urls.py         # URL routing
templates/             # HTML templates (base, home, detail, continent, category)
static/               # CSS, JS, images
celeryapp.py          # Celery configuration
manage.py             # Django CLI
requirements.txt      # Python dependencies
.env                  # Environment configuration
README.md             # Full documentation
QUICKSTART.md         # Quick setup guide
PROJECT_OVERVIEW.md   # Project overview
```

## URLs & Access
- **Frontend**: http://127.0.0.1:8000/
- **Admin**: http://127.0.0.1:8000/admin/
- **API**: http://127.0.0.1:8000/api/articles/
- **By Continent**: http://127.0.0.1:8000/continent/AS/
- **By Category**: http://127.0.0.1:8000/category/TECHNOLOGY/

## Development Guidelines
- Follow Django best practices and PEP 8
- Use class-based views for consistency
- Keep business logic in services
- Use Celery tasks for background operations
- Write tests for critical functionality
- Use environment variables for sensitive data
- Keep AI processing asynchronous

## Next Steps for User
1. Create superuser: `python manage.py createsuperuser`
2. Configure AI API keys in `.env` (optional)
3. Set up Redis for auto-refresh
4. Start Celery worker and beat
5. Manually fetch initial news or wait 2 minutes

## Common Tasks
- **Fetch news manually**: Run `test_news_fetch.py` or via Python shell
- **Add categories**: Edit `news/models.py` Category choices
- **Customize UI**: Modify templates in `templates/news/`
- **Add news sources**: Via admin panel
- **API testing**: Use browsable API at http://127.0.0.1:8000/api/
