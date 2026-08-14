"""AI API routes."""
from django.urls import path

from apps.ai.views import ChatView, RecommendationsView, SmartSearchView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("recommendations/", RecommendationsView.as_view(), name="ai-recommendations"),
    path("search/", SmartSearchView.as_view(), name="ai-search"),
]
