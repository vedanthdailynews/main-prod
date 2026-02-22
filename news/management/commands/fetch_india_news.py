"""
Management command to fetch India news directly from publisher RSS feeds.
Usage:
    python manage.py fetch_india_news              # national + categories + states
    python manage.py fetch_india_news --national   # only national feeds
    python manage.py fetch_india_news --state TN   # only Tamil Nadu feeds
    python manage.py fetch_india_news --all        # same as default
"""
from django.core.management.base import BaseCommand
from news.services import IndiaNewsService


class Command(BaseCommand):
    help = 'Fetch India news directly from The Hindu, TOI, NDTV, IE, HT and regional feeds'

    def add_arguments(self, parser):
        parser.add_argument('--national', action='store_true', help='Fetch national feeds only')
        parser.add_argument('--categories', action='store_true', help='Fetch category feeds only')
        parser.add_argument('--state', type=str, default='', help='Fetch feeds for a specific state code (e.g. TN, KA)')
        parser.add_argument('--all', action='store_true', default=True, help='Fetch all India feeds (default)')

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('=== India-First News Fetch ==='))

        if options['national']:
            count = IndiaNewsService.fetch_national()
            self.stdout.write(self.style.SUCCESS(f'National feeds: {count} new articles'))

        elif options['categories']:
            count = IndiaNewsService.fetch_categories()
            self.stdout.write(self.style.SUCCESS(f'Category feeds: {count} new articles'))

        elif options['state']:
            state = options['state'].upper()
            feeds = IndiaNewsService.STATE_FEEDS.get(state)
            if not feeds:
                self.stdout.write(self.style.ERROR(f'No feeds configured for state: {state}'))
                self.stdout.write(f'Available: {", ".join(IndiaNewsService.STATE_FEEDS.keys())}')
                return
            total = 0
            for source, url, cat in feeds:
                count = IndiaNewsService._fetch_feed(source, url, cat, state_code=state)
                total += count
                self.stdout.write(f'  {source}: {count} new articles')
            self.stdout.write(self.style.SUCCESS(f'{state} total: {total} new articles'))

        else:
            # Full run
            self.stdout.write('Fetching national feeds...')
            nat = IndiaNewsService.fetch_national()
            self.stdout.write(self.style.SUCCESS(f'  National: {nat} new articles'))

            self.stdout.write('Fetching category feeds...')
            cat = IndiaNewsService.fetch_categories()
            self.stdout.write(self.style.SUCCESS(f'  Categories: {cat} new articles'))

            self.stdout.write('Fetching state/city feeds...')
            state_results = IndiaNewsService.fetch_states()
            for state_code, count in state_results.items():
                if count > 0:
                    state_name = state_code
                    from news.models import IndianState
                    state_name = dict(IndianState.choices).get(state_code, state_code)
                    self.stdout.write(f'  {state_name}: {count} new articles')

            total = nat + cat + sum(state_results.values())
            self.stdout.write(self.style.SUCCESS(f'\n✓ Total new articles fetched: {total}'))
