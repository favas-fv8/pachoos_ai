"""AI views — chat, recommendations, smart search."""
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.serializers import (
    ChatMessageSerializer,
    ChatResponseSerializer,
    RecommendationSerializer,
    SmartSearchSerializer,
)
from apps.ai.services import chat_assistant, get_recommendations, smart_search
from apps.catalog.serializers import ProductListSerializer


CHAT_SUGGESTIONS = [
    "What do you recommend?",
    "Do you have any cakes?",
    "What's on sale today?",
    "How does delivery work?",
    "Tell me about your wallet",
]


class ChatView(APIView):
    """AI chat assistant endpoint."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChatMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user if request.user.is_authenticated else None

        response_text = chat_assistant(
            message=data["message"],
            user=user,
            history=data.get("history", []),
        )

        return Response({
            "response": response_text,
            "suggestions": CHAT_SUGGESTIONS,
        })


class RecommendationsView(APIView):
    """Product recommendations endpoint."""

    permission_classes = [AllowAny]

    def get(self, request):
        product_id = request.query_params.get("product_id")
        limit = int(request.query_params.get("limit", 8))

        user = request.user if request.user.is_authenticated else None

        products = get_recommendations(
            user=user,
            product_id=product_id,
            limit=min(limit, 20),
        )

        return Response(ProductListSerializer(products, many=True).data)


class SmartSearchView(APIView):
    """Smart search with natural language understanding."""

    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "")
        limit = int(request.query_params.get("limit", 20))

        if not q.strip():
            return Response([])

        products = smart_search(q, limit=min(limit, 50))
        return Response(ProductListSerializer(products, many=True).data)
