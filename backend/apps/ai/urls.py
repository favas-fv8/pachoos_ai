"""AI API routes."""
from django.urls import path

from apps.ai.views import (
    AdminChatView,
    ChatView,
    RecommendationsView,
    SmartSearchView,
)

urlpatterns = [
    # Customer audience (customer-side data only).
    path("chat/", ChatView.as_view(), name="ai-chat"),
    # Admin audience (IsAdmin; admin-side data only).
    path("admin-chat/", AdminChatView.as_view(), name="ai-admin-chat"),
    path("recommendations/", RecommendationsView.as_view(), name="ai-recommendations"),
    path("search/", SmartSearchView.as_view(), name="ai-search"),
]
