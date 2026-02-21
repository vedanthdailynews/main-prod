"""
URL configuration for news app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from news.views import (
    HomePageView,
    ContinentNewsView,
    CategoryNewsView,
    StateNewsView,
    IndiaNewsView,
    NewsDetailView,
    BudgetNewsView,
    EPaperView,
    AQIView,
    NewsArticleViewSet,
    NewsSourceViewSet,
    StockMarketView,
)

# REST API router
router = DefaultRouter()
router.register(r'articles', NewsArticleViewSet, basename='article')
router.register(r'sources', NewsSourceViewSet, basename='source')

app_name = 'news'

urlpatterns = [
    # Template views
    path('', HomePageView.as_view(), name='home'),
    path('epaper/', EPaperView.as_view(), name='epaper'),
    path('aqi/', AQIView.as_view(), name='aqi'),
    path('budget/', BudgetNewsView.as_view(), name='budget_home'),
    path('india/', IndiaNewsView.as_view(), name='india'),
    path('continent/<str:continent>/', ContinentNewsView.as_view(), name='continent'),
    path('category/<str:category>/', CategoryNewsView.as_view(), name='category'),
    path('state/<str:state>/', StateNewsView.as_view(), name='state'),
    path('article/<int:pk>/', NewsDetailView.as_view(), name='detail'),
    
    # API endpoints
    path('api/', include(router.urls)),
    path('api/stocks/', StockMarketView.as_view(), name='stocks'),
]
