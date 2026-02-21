"""
Views for news application.
"""
import logging
from datetime import datetime

from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, TemplateView
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from news.models import NewsArticle, NewsSource, Continent, Category, IndianState, DailyPaper
from news.serializers import (
    NewsArticleSerializer,
    NewsArticleListSerializer,
    NewsSourceSerializer
)
from news.tasks import fetch_all_news, process_article_with_ai
from news.stock_service import StockMarketService

logger = logging.getLogger(__name__)


# Django Template Views
class HomePageView(ListView):
    """Homepage showing latest news — India first, then international."""
    model = NewsArticle
    template_name = 'news/home.html'
    context_object_name = 'articles'
    paginate_by = 24

    def get_queryset(self):
        # Default paginated list: India first, then rest sorted by date
        from django.db.models import Case, When, IntegerField
        return (
            NewsArticle.objects
            .annotate(
                india_priority=Case(
                    When(is_indian_news=True, then=0),
                    When(continent='AS', then=0),
                    default=1,
                    output_field=IntegerField(),
                )
            )
            .order_by('india_priority', '-published_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # If DB is empty (e.g. first request after a cold start or fresh deploy),
        # trigger a synchronous news fetch so the page isn't blank.
        if not NewsArticle.objects.exists():
            try:
                from news.services import GoogleNewsService
                import threading
                threading.Thread(
                    target=GoogleNewsService.fetch_all_news, daemon=True
                ).start()
                context['fetching_now'] = True
            except Exception:
                pass

        # India section – top 12 latest Indian articles
        context['india_articles'] = (
            NewsArticle.objects
            .filter(is_indian_news=True)
            .order_by('-published_at')[:12]
        )
        # If no is_indian_news flagged yet, fall back to AS continent
        if not context['india_articles'].exists():
            context['india_articles'] = (
                NewsArticle.objects
                .filter(continent='AS')
                .order_by('-published_at')[:12]
            )

        # International section – top 12 non-India articles
        context['international_articles'] = (
            NewsArticle.objects
            .exclude(is_indian_news=True)
            .exclude(continent='AS')
            .order_by('-published_at')[:12]
        )

        # Featured / hero article – prefer Indian news
        context['hero_article'] = (
            NewsArticle.objects
            .filter(is_indian_news=True)
            .order_by('-published_at')
            .first()
            or NewsArticle.objects.order_by('-published_at').first()
        )

        # Trending sidebar – mix of India + World
        context['trending_articles'] = (
            NewsArticle.objects.order_by('-published_at')[:8]
        )

        context['continents'] = Continent.choices
        context['categories'] = Category.choices
        context['indian_states'] = IndianState.choices
        return context


class ContinentNewsView(ListView):
    """News filtered by continent."""
    model = NewsArticle
    template_name = 'news/continent.html'
    context_object_name = 'articles'
    paginate_by = 20
    
    def get_queryset(self):
        continent = self.kwargs.get('continent')
        return NewsArticle.objects.filter(continent=continent)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['continent'] = self.kwargs.get('continent')
        context['continent_name'] = dict(Continent.choices).get(self.kwargs.get('continent'))
        return context


class CategoryNewsView(ListView):
    """News filtered by category."""
    model = NewsArticle
    template_name = 'news/category.html'
    context_object_name = 'articles'
    paginate_by = 20
    
    def get_queryset(self):
        category = self.kwargs.get('category')
        return NewsArticle.objects.filter(category=category)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = self.kwargs.get('category')
        context['category_name'] = dict(Category.choices).get(self.kwargs.get('category'))
        return context


class StateNewsView(ListView):
    """News filtered by Indian state."""
    model = NewsArticle
    template_name = 'news/state.html'
    context_object_name = 'articles'
    paginate_by = 20
    
    def get_queryset(self):
        state = self.kwargs.get('state')
        return NewsArticle.objects.filter(indian_state=state)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['state'] = self.kwargs.get('state')
        context['state_name'] = dict(IndianState.choices).get(self.kwargs.get('state'))
        return context


class IndiaNewsView(ListView):
    """News filtered for India - shows all Indian news."""
    model = NewsArticle
    template_name = 'news/india.html'
    context_object_name = 'articles'
    paginate_by = 20
    
    def get_queryset(self):
        return NewsArticle.objects.filter(is_indian_news=True).order_by('-published_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_articles'] = NewsArticle.objects.filter(is_indian_news=True).count()
        context['indian_states'] = IndianState.choices
        return context


class NewsDetailView(DetailView):
    """Detail view for a single news article."""
    model = NewsArticle
    template_name = 'news/detail.html'
    context_object_name = 'article'
    
    def get_object(self):
        article = super().get_object()
        # Increment view count
        article.view_count += 1
        article.save(update_fields=['view_count'])
        return article


class BudgetNewsView(ListView):
    """Budget 2026 dedicated page view."""
    model = NewsArticle
    template_name = 'news/budget.html'
    context_object_name = 'articles'
    paginate_by = 18
    
    def get_queryset(self):
        return NewsArticle.objects.filter(
            category='BUDGET'
        ).order_by('-published_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get featured budget article
        context['featured_article'] = NewsArticle.objects.filter(
            category='BUDGET'
        ).order_by('-published_at').first()
        return context
    context_object_name = 'article'
    
    def get_object(self):
        obj = super().get_object()
        obj.increment_views()
        return obj


# REST API ViewSets
class NewsArticleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for news articles.
    
    Supports filtering by continent, category, and search.
    """
    queryset = NewsArticle.objects.all()
    serializer_class = NewsArticleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['continent', 'category', 'is_featured', 'sentiment']
    search_fields = ['title', 'description', 'source']
    ordering_fields = ['published_at', 'view_count', 'created_at']
    ordering = ['-published_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NewsArticleListSerializer
        return NewsArticleSerializer
    
    @action(detail=False, methods=['get'])
    def by_continent(self, request):
        """Get news grouped by continent."""
        continent = request.query_params.get('continent')
        if not continent:
            return Response(
                {'error': 'continent parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        articles = self.queryset.filter(continent=continent)
        page = self.paginate_queryset(articles)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(articles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured articles."""
        articles = self.queryset.filter(is_featured=True)
        serializer = self.get_serializer(articles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending articles based on view count."""
        articles = self.queryset.order_by('-view_count')[:10]
        serializer = self.get_serializer(articles, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def process_with_ai(self, request, pk=None):
        """Trigger AI processing for a specific article."""
        article = self.get_object()
        process_article_with_ai.delay(article.id)
        return Response({'message': 'AI processing queued'})
    
    @action(detail=False, methods=['post'])
    def fetch_news(self, request):
        """Trigger news fetching from Google News."""
        fetch_all_news.delay()
        return Response({'message': 'News fetch queued'})


class NewsSourceViewSet(viewsets.ModelViewSet):
    """API endpoint for news sources."""
    queryset = NewsSource.objects.all()
    serializer_class = NewsSourceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['continent', 'is_active']
    search_fields = ['name']


# Stock Market API View
class StockMarketView(APIView):
    """API endpoint for live stock market data."""
    
    def get(self, request):
        """Get live NIFTY indices data."""
        try:
            market_data = StockMarketService.get_live_market_data()
            return Response({
                'success': True,
                'data': market_data,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error in StockMarketView: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=500)


class EPaperView(ListView):
    """Digital ePaper view with Print View (PDF) and Digital View options."""
    model = DailyPaper
    template_name = 'news/epaper.html'
    context_object_name = 'daily_paper'
    
    def get_queryset(self):
        # Get date from query params or use today
        date_str = self.request.GET.get('date')
        
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                from django.utils import timezone
                date_obj = timezone.now().date()
        else:
            from django.utils import timezone
            date_obj = timezone.now().date()
        
        # Get daily paper for the date
        return DailyPaper.objects.filter(date=date_obj, is_published=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.utils import timezone
        
        # Current date and view mode
        current_date_str = self.request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
        context['current_date'] = current_date_str
        context['view_mode'] = self.request.GET.get('view', 'print')  # 'print' or 'digital'
        
        # Get daily paper for current date
        try:
            date_obj = datetime.strptime(current_date_str, '%Y-%m-%d').date()
            daily_paper = DailyPaper.objects.filter(date=date_obj, is_published=True).first()
            context['paper'] = daily_paper
        except (ValueError, DailyPaper.DoesNotExist):
            context['paper'] = None
        
        # For digital view, get articles from PDF or database
        if context['view_mode'] == 'digital':
            try:
                date_obj = datetime.strptime(current_date_str, '%Y-%m-%d').date()
                page = int(self.request.GET.get('page', '1'))
                
                # First, try to get articles from uploaded PDF
                daily_paper = context.get('paper')
                if daily_paper and daily_paper.pdf_content:
                    # Use PDF-extracted content
                    all_pdf_articles = daily_paper.pdf_content
                    
                    # Paginate: show 9 articles per page
                    articles_per_page = 9
                    start_idx = (page - 1) * articles_per_page
                    end_idx = start_idx + articles_per_page
                    
                    context['pdf_articles'] = all_pdf_articles[start_idx:end_idx]
                    context['current_page'] = page
                    context['total_pages'] = (len(all_pdf_articles) + articles_per_page - 1) // articles_per_page
                    context['source'] = 'pdf'
                else:
                    # Fallback to database articles
                    section = self.request.GET.get('section', 'FRONT_PAGE')
                    articles_queryset = NewsArticle.objects.filter(published_at__date=date_obj)
                    
                    # Filter by page
                    articles_queryset = articles_queryset.filter(epaper_page=page)
                    
                    # Filter by section if not "ALL"
                    if section != 'ALL':
                        articles_queryset = articles_queryset.filter(epaper_section=section)
                    
                    context['articles'] = articles_queryset.order_by('epaper_position', '-published_at')
                    context['current_page'] = page
                    context['current_section'] = section
                    
                    # Get total pages
                    max_page = NewsArticle.objects.filter(published_at__date=date_obj).values_list('epaper_page', flat=True).distinct().order_by('-epaper_page').first()
                    context['total_pages'] = max_page if max_page else 1
                    context['source'] = 'database'
                
                # Sections
                context['sections'] = [
                    ('FRONT_PAGE', 'Front Page'),
                    ('CITY', 'City'),
                    ('NATION', 'Nation'),
                    ('WORLD', 'World'),
                    ('BUSINESS', 'Business'),
                    ('SPORTS', 'Sports'),
                    ('ENTERTAINMENT', 'Entertainment'),
                ]
            except ValueError:
                context['articles'] = []
                context['total_pages'] = 1
        
        # Available dates with papers
        context['available_dates'] = DailyPaper.objects.filter(is_published=True).values_list('date', flat=True).distinct().order_by('-date')[:30]
        
        return context

class AQIView(TemplateView):
    """Live Air Quality Index page for global cities."""
    template_name = 'news/aqi.html'

    # Each city: name, lat, lon, country
    CITIES = [
        # ── India ────────────────────────────────────────────────────────
        {"name": "Delhi",         "lat": 28.6519,  "lon": 77.2315,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Mumbai",        "lat": 19.0760,  "lon": 72.8777,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Kolkata",       "lat": 22.5726,  "lon": 88.3639,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Chennai",       "lat": 13.0827,  "lon": 80.2707,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Bangalore",     "lat": 12.9716,  "lon": 77.5946,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Hyderabad",     "lat": 17.3850,  "lon": 78.4867,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Pune",          "lat": 18.5204,  "lon": 73.8567,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Ahmedabad",     "lat": 23.0225,  "lon": 72.5714,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Jaipur",        "lat": 26.9124,  "lon": 75.7873,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Lucknow",       "lat": 26.8467,  "lon": 80.9462,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Kanpur",        "lat": 26.4499,  "lon": 80.3319,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Patna",         "lat": 25.5941,  "lon": 85.1376,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Varanasi",      "lat": 25.3176,  "lon": 82.9739,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Agra",          "lat": 27.1767,  "lon": 78.0081,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Bhopal",        "lat": 23.2599,  "lon": 77.4126,  "country": "India",       "region": "🇮🇳 India"},
        {"name": "Nagpur",        "lat": 21.1458,  "lon": 79.0882,  "country": "India",       "region": "🇮🇳 India"},
        # ── Asia-Pacific ─────────────────────────────────────────────────
        {"name": "Beijing",       "lat": 39.9042,  "lon": 116.4074, "country": "China",       "region": "🌏 Asia-Pacific"},
        {"name": "Shanghai",      "lat": 31.2304,  "lon": 121.4737, "country": "China",       "region": "🌏 Asia-Pacific"},
        {"name": "Guangzhou",     "lat": 23.1291,  "lon": 113.2644, "country": "China",       "region": "🌏 Asia-Pacific"},
        {"name": "Tokyo",         "lat": 35.6762,  "lon": 139.6503, "country": "Japan",       "region": "🌏 Asia-Pacific"},
        {"name": "Seoul",         "lat": 37.5665,  "lon": 126.9780, "country": "S. Korea",    "region": "🌏 Asia-Pacific"},
        {"name": "Bangkok",       "lat": 13.7563,  "lon": 100.5018, "country": "Thailand",    "region": "🌏 Asia-Pacific"},
        {"name": "Singapore",     "lat": 1.3521,   "lon": 103.8198, "country": "Singapore",   "region": "🌏 Asia-Pacific"},
        {"name": "Jakarta",       "lat": -6.2088,  "lon": 106.8456, "country": "Indonesia",   "region": "🌏 Asia-Pacific"},
        {"name": "Manila",        "lat": 14.5995,  "lon": 120.9842, "country": "Philippines", "region": "🌏 Asia-Pacific"},
        {"name": "Dhaka",         "lat": 23.8103,  "lon": 90.4125,  "country": "Bangladesh",  "region": "🌏 Asia-Pacific"},
        {"name": "Karachi",       "lat": 24.8607,  "lon": 67.0011,  "country": "Pakistan",    "region": "🌏 Asia-Pacific"},
        {"name": "Taipei",        "lat": 25.0330,  "lon": 121.5654, "country": "Taiwan",      "region": "🌏 Asia-Pacific"},
        {"name": "Kuala Lumpur",  "lat": 3.1390,   "lon": 101.6869, "country": "Malaysia",    "region": "🌏 Asia-Pacific"},
        {"name": "Ho Chi Minh",   "lat": 10.8231,  "lon": 106.6297, "country": "Vietnam",     "region": "🌏 Asia-Pacific"},
        {"name": "Kathmandu",     "lat": 27.7172,  "lon": 85.3240,  "country": "Nepal",       "region": "🌏 Asia-Pacific"},
        # ── Middle East & Africa ─────────────────────────────────────────
        {"name": "Dubai",         "lat": 25.2048,  "lon": 55.2708,  "country": "UAE",         "region": "🌍 Middle East & Africa"},
        {"name": "Riyadh",        "lat": 24.7136,  "lon": 46.6753,  "country": "Saudi Arabia","region": "🌍 Middle East & Africa"},
        {"name": "Cairo",         "lat": 30.0444,  "lon": 31.2357,  "country": "Egypt",       "region": "🌍 Middle East & Africa"},
        {"name": "Tehran",        "lat": 35.6892,  "lon": 51.3890,  "country": "Iran",        "region": "🌍 Middle East & Africa"},
        {"name": "Doha",          "lat": 25.2854,  "lon": 51.5310,  "country": "Qatar",       "region": "🌍 Middle East & Africa"},
        {"name": "Istanbul",      "lat": 41.0082,  "lon": 28.9784,  "country": "Turkey",      "region": "🌍 Middle East & Africa"},
        {"name": "Johannesburg",  "lat": -26.2041, "lon": 28.0473,  "country": "S. Africa",   "region": "🌍 Middle East & Africa"},
        {"name": "Nairobi",       "lat": -1.2921,  "lon": 36.8219,  "country": "Kenya",       "region": "🌍 Middle East & Africa"},
        {"name": "Lagos",         "lat": 6.5244,   "lon": 3.3792,   "country": "Nigeria",     "region": "🌍 Middle East & Africa"},
        {"name": "Casablanca",    "lat": 33.5731,  "lon": -7.5898,  "country": "Morocco",     "region": "🌍 Middle East & Africa"},
        # ── Europe ───────────────────────────────────────────────────────
        {"name": "London",        "lat": 51.5074,  "lon": -0.1278,  "country": "UK",          "region": "🌍 Europe"},
        {"name": "Paris",         "lat": 48.8566,  "lon": 2.3522,   "country": "France",      "region": "🌍 Europe"},
        {"name": "Berlin",        "lat": 52.5200,  "lon": 13.4050,  "country": "Germany",     "region": "🌍 Europe"},
        {"name": "Madrid",        "lat": 40.4168,  "lon": -3.7038,  "country": "Spain",       "region": "🌍 Europe"},
        {"name": "Rome",          "lat": 41.9028,  "lon": 12.4964,  "country": "Italy",       "region": "🌍 Europe"},
        {"name": "Amsterdam",     "lat": 52.3676,  "lon": 4.9041,   "country": "Netherlands", "region": "🌍 Europe"},
        {"name": "Warsaw",        "lat": 52.2297,  "lon": 21.0122,  "country": "Poland",      "region": "🌍 Europe"},
        {"name": "Moscow",        "lat": 55.7558,  "lon": 37.6173,  "country": "Russia",      "region": "🌍 Europe"},
        {"name": "Kyiv",          "lat": 50.4501,  "lon": 30.5234,  "country": "Ukraine",     "region": "🌍 Europe"},
        {"name": "Athens",        "lat": 37.9838,  "lon": 23.7275,  "country": "Greece",      "region": "🌍 Europe"},
        {"name": "Bucharest",     "lat": 44.4268,  "lon": 26.1025,  "country": "Romania",     "region": "🌍 Europe"},
        # ── Americas ─────────────────────────────────────────────────────
        {"name": "New York",      "lat": 40.7128,  "lon": -74.0060, "country": "USA",         "region": "🌎 Americas"},
        {"name": "Los Angeles",   "lat": 34.0522,  "lon": -118.2437,"country": "USA",         "region": "🌎 Americas"},
        {"name": "Chicago",       "lat": 41.8781,  "lon": -87.6298, "country": "USA",         "region": "🌎 Americas"},
        {"name": "Toronto",       "lat": 43.6532,  "lon": -79.3832, "country": "Canada",      "region": "🌎 Americas"},
        {"name": "São Paulo",     "lat": -23.5505, "lon": -46.6333, "country": "Brazil",      "region": "🌎 Americas"},
        {"name": "Mexico City",   "lat": 19.4326,  "lon": -99.1332, "country": "Mexico",      "region": "🌎 Americas"},
        {"name": "Buenos Aires",  "lat": -34.6037, "lon": -58.3816, "country": "Argentina",   "region": "🌎 Americas"},
        {"name": "Bogotá",        "lat": 4.7110,   "lon": -74.0721, "country": "Colombia",    "region": "🌎 Americas"},
        {"name": "Lima",          "lat": -12.0464, "lon": -77.0428, "country": "Peru",        "region": "🌎 Americas"},
        # ── Oceania ──────────────────────────────────────────────────────
        {"name": "Sydney",        "lat": -33.8688, "lon": 151.2093, "country": "Australia",   "region": "🌏 Oceania"},
        {"name": "Melbourne",     "lat": -37.8136, "lon": 144.9631, "country": "Australia",   "region": "🌏 Oceania"},
        {"name": "Brisbane",      "lat": -27.4698, "lon": 153.0251, "country": "Australia",   "region": "🌏 Oceania"},
        {"name": "Auckland",      "lat": -36.8509, "lon": 174.7645, "country": "New Zealand", "region": "🌏 Oceania"},
    ]

    # Build ordered region → cities dict for template
    REGION_ORDER = [
        "🇮🇳 India", "🌏 Asia-Pacific", "🌍 Middle East & Africa",
        "🌍 Europe", "🌎 Americas", "🌏 Oceania",
    ]

    def get_context_data(self, **kwargs):
        import json
        context = super().get_context_data(**kwargs)
        # Group cities by region preserving order
        regions = {r: [] for r in self.REGION_ORDER}
        for city in self.CITIES:
            regions[city["region"]].append(city)
        context['regions'] = regions
        context['cities_json'] = json.dumps(self.CITIES)
        context['total_cities'] = len(self.CITIES)
        return context