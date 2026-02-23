from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class NewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'news'

    def ready(self):
        """Start the APScheduler background scheduler when Django starts.
        This fetches news every 5 minutes without needing Redis or Celery.
        """
        import os
        from django.conf import settings

        # In development with auto-reloader, Django spawns a child process
        # with RUN_MAIN=true — only run scheduler in that child to avoid duplicates.
        # In production (gunicorn on Render), RUN_MAIN is not set, so we check
        # DEBUG to decide: dev requires RUN_MAIN, production always starts.
        if settings.DEBUG and os.environ.get('RUN_MAIN') != 'true':
            return

        # Guard against multiple workers starting duplicate schedulers.
        # Only the first process to set this env var will run the scheduler.
        if os.environ.get('APSCHEDULER_STARTED') == 'true':
            return
        os.environ['APSCHEDULER_STARTED'] = 'true'

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger
            from django.utils import timezone

            def fetch_news_job():
                """Fetch latest news from Google News RSS feeds."""
                try:
                    from news.services import GoogleNewsService
                    logger.info("[Scheduler] Starting news fetch...")
                    results = GoogleNewsService.fetch_all_news()
                    total = sum(results.values())
                    logger.info(f"[Scheduler] Fetch complete. {total} new articles added.")
                except Exception as e:
                    logger.error(f"[Scheduler] News fetch failed: {e}")

            scheduler = BackgroundScheduler(timezone=timezone.get_current_timezone())
            scheduler.add_job(
                fetch_news_job,
                trigger=IntervalTrigger(minutes=5),
                id='fetch_news_every_5_minutes',
                name='Fetch Google News every 5 minutes',
                replace_existing=True,
            )
            scheduler.start()
            logger.info("[Scheduler] APScheduler started — fetching news every 5 minutes.")

            # Fetch immediately on startup
            import threading
            threading.Thread(target=fetch_news_job, daemon=True).start()

        except Exception as e:
            logger.error(f"[Scheduler] Failed to start scheduler: {e}")
