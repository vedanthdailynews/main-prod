# Deployment Guide - Vedant Daily News

## Production Deployment Checklist

### 1. Security Configuration

#### Update Environment Variables (.env)
```env
# CRITICAL: Change these for production!
DEBUG=False
SECRET_KEY=your-strong-random-secret-key-here-min-50-chars
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (PostgreSQL recommended)
DATABASE_URL=postgresql://user:password@localhost:5432/vedant_news

# Redis
REDIS_URL=redis://localhost:6379/0

# AI Keys
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key

# Security
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

#### Generate Strong Secret Key
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 2. Database Setup (PostgreSQL)

#### Install PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# Install Python adapter
pip install psycopg2-binary
```

#### Create Database
```bash
sudo -u postgres psql
CREATE DATABASE vedant_news;
CREATE USER vedant_user WITH PASSWORD 'strong_password';
ALTER ROLE vedant_user SET client_encoding TO 'utf8';
ALTER ROLE vedant_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE vedant_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE vedant_news TO vedant_user;
\q
```

#### Update settings.py
```python
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600
    )
}
```

### 3. Static Files Configuration

#### settings.py
```python
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'

MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# WhiteNoise for serving static files
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add this
    # ... other middleware
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

#### Install WhiteNoise
```bash
pip install whitenoise
```

#### Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 4. Web Server Setup

#### Option A: Gunicorn + Nginx

**Install Gunicorn**
```bash
pip install gunicorn
```

**Create gunicorn_config.py**
```python
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2
```

**Run Gunicorn**
```bash
gunicorn vedant_news.wsgi:application -c gunicorn_config.py
```

**Nginx Configuration** (`/etc/nginx/sites-available/vedant_news`)
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        alias /path/to/project/staticfiles/;
    }
    
    location /media/ {
        alias /path/to/project/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable site**
```bash
sudo ln -s /etc/nginx/sites-available/vedant_news /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. Process Management (Systemd)

#### Django Service (`/etc/systemd/system/vedant_news.service`)
```ini
[Unit]
Description=Vedant Daily News Django
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/.venv/bin"
ExecStart=/path/to/project/.venv/bin/gunicorn vedant_news.wsgi:application -c gunicorn_config.py
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

#### Celery Worker Service (`/etc/systemd/system/vedant_news_celery.service`)
```ini
[Unit]
Description=Vedant Daily News Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/.venv/bin"
ExecStart=/path/to/project/.venv/bin/celery -A celeryapp worker --loglevel=info --detach
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Celery Beat Service (`/etc/systemd/system/vedant_news_celery_beat.service`)
```ini
[Unit]
Description=Vedant Daily News Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/project/.venv/bin"
ExecStart=/path/to/project/.venv/bin/celery -A celeryapp beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable vedant_news
sudo systemctl enable vedant_news_celery
sudo systemctl enable vedant_news_celery_beat
sudo systemctl start vedant_news
sudo systemctl start vedant_news_celery
sudo systemctl start vedant_news_celery_beat
```

### 6. SSL/HTTPS Setup (Let's Encrypt)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal is configured automatically
# Test renewal
sudo certbot renew --dry-run
```

### 7. Redis Setup

```bash
# Install Redis
sudo apt-get install redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
# Set: supervised systemd
# Set: bind 127.0.0.1 ::1
# Set: requirepass your_strong_password

# Start Redis
sudo systemctl enable redis
sudo systemctl start redis

# Update REDIS_URL in .env
REDIS_URL=redis://:your_strong_password@localhost:6379/0
```

### 8. Logging Configuration

#### Update settings.py
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/vedant_news/django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'celery': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/vedant_news/celery.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'celery': {
            'handlers': ['celery'],
            'level': 'INFO',
        },
        'news': {
            'handlers': ['file'],
            'level': 'INFO',
        },
    },
}
```

#### Create log directory
```bash
sudo mkdir -p /var/log/vedant_news
sudo chown www-data:www-data /var/log/vedant_news
```

### 9. Monitoring & Maintenance

#### Database Backups
```bash
#!/bin/bash
# backup_db.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump vedant_news > /backups/vedant_news_$DATE.sql
# Keep only last 7 days
find /backups -name "vedant_news_*.sql" -mtime +7 -delete
```

#### Add to crontab
```bash
# Backup database daily at 2 AM
0 2 * * * /path/to/backup_db.sh
```

#### Health Check Endpoint
Add to `news/views.py`:
```python
from django.http import JsonResponse
from django.views.decorators.cache import never_cache

@never_cache
def health_check(request):
    return JsonResponse({'status': 'healthy'})
```

### 10. Performance Optimization

#### settings.py additions
```python
# Caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL'),
    }
}

# Session storage
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Security
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
```

### 11. Deployment Commands

```bash
# Update code
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart vedant_news
sudo systemctl restart vedant_news_celery
sudo systemctl restart vedant_news_celery_beat
```

### 12. Platform-Specific Deployment

#### Heroku
```bash
# Install Heroku CLI and login
heroku login

# Create app
heroku create vedant-news

# Add PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# Add Redis
heroku addons:create heroku-redis:hobby-dev

# Set environment variables
heroku config:set DEBUG=False
heroku config:set SECRET_KEY=your-secret-key
heroku config:set OPENAI_API_KEY=your-key

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate

# Create superuser
heroku run python manage.py createsuperuser
```

#### Docker
See `Dockerfile` and `docker-compose.yml` (create if needed)

### 13. Monitoring Tools

- **Sentry**: Error tracking
- **New Relic**: Application monitoring
- **Datadog**: Infrastructure monitoring
- **Uptime Robot**: Uptime monitoring

### 14. Post-Deployment

1. Test all functionality
2. Verify Celery tasks are running
3. Check logs for errors
4. Test API endpoints
5. Verify SSL certificate
6. Test backup restoration
7. Set up monitoring alerts
8. Document deployment process

## Quick Production Deployment (Ubuntu)

```bash
# 1. System updates
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install dependencies
sudo apt-get install -y python3-pip python3-venv postgresql redis-server nginx

# 3. Clone project
git clone <your-repo> /var/www/vedant_news
cd /var/www/vedant_news

# 4. Virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
nano .env  # Edit with production values

# 6. Database setup
sudo -u postgres psql
# Run CREATE DATABASE commands

# 7. Django setup
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser

# 8. Configure services (systemd, nginx)
# Copy service files from above

# 9. Start services
sudo systemctl start vedant_news
sudo systemctl start vedant_news_celery
sudo systemctl start vedant_news_celery_beat

# 10. Setup SSL
sudo certbot --nginx -d yourdomain.com
```

---

**Important**: Always test deployment in a staging environment first!
