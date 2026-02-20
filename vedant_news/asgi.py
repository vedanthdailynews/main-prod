"""
ASGI config for vedant_news project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vedant_news.settings')

application = get_asgi_application()
