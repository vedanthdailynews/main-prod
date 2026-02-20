"""
Management command to fetch news from Google News RSS feeds.
Run with: python manage.py fetch_news
"""
from django.core.management.base import BaseCommand
from news.services import GoogleNewsService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetch latest news from Google News RSS feeds for all continents and categories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--india-only',
            action='store_true',
            help='Fetch India news only',
        )

    def handle(self, *args, **options):
        self.stdout.write('Fetching news from Google News...')
        try:
            if options.get('india_only'):
                count = GoogleNewsService.fetch_news_for_continent('AS')
                results = {'AS': count}
            else:
                results = GoogleNewsService.fetch_all_news()

            total = sum(results.values())
            for continent, count in results.items():
                if count:
                    self.stdout.write(f'  {continent}: {count} new articles')

            self.stdout.write(
                self.style.SUCCESS(f'Done. Total new articles fetched: {total}')
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error fetching news: {e}'))
            raise
