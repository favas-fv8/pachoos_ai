"""AI views — chat assistants (customer/admin), recommendations, smart search."""
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
from apps.ai.services import (
    admin_chat_assistant,
    chat_assistant,
    get_recommendations,
    smart_search,
)
from apps.catalog.serializers import ProductListSerializer
from apps.core.permissions import IsAdmin


CHAT_SUGGESTIONS = [
    "What do you recommend?",
    "Do you have any cakes?",
    "Where is my order?",
    "How does delivery work?",
    "What's my cashback balance?",
]

ADMIN_CHAT_SUGGESTIONS = [
    "What's the monthly revenue?",
    "How many orders this month?",
    "Any low stock items?",
    "How many pending orders?",
    "How many customers do we have?",
]


class ChatView(APIView):
    """AI chat assistant endpoint — CUSTOMER audience only.

    The audience is decided server-side: personal context is attached only for
    authenticated non-staff users. Admin/staff callers are treated as guest
    shoppers here and must use /admin-chat/ for internal data.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChatMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user if request.user.is_authenticated else None
        if user is not None and getattr(user, "is_staff", False):
            # Staff on the customer endpoint never receive personal grounding.
            user = None

        response_text = chat_assistant(
            message=data["message"],
            user=user,
            history=data.get("history", []),
            delivery_location=data.get("location"),
        )

        return Response({
            "response": response_text,
            "suggestions": CHAT_SUGGESTIONS,
        })


class AdminChatView(APIView):
    """AI chat assistant endpoint — ADMIN audience only.

    Requires an authenticated admin (super_admin / store_manager) via RBAC.
    Answers come exclusively from live admin-side data scoped to the shop.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = ChatMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        response_text = admin_chat_assistant(
            message=data["message"],
            history=data.get("history", []),
            shop=getattr(request, "shop", None),
            user=request.user,
        )

        return Response({
            "response": response_text,
            "suggestions": ADMIN_CHAT_SUGGESTIONS,
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
