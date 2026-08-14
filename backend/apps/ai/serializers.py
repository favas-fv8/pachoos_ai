"""AI serializers."""
from rest_framework import serializers


class ChatMessageSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000)
    history = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
    )


class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    suggestions = serializers.ListField(child=serializers.CharField(), required=False)


class RecommendationSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=False, allow_null=True)
    limit = serializers.IntegerField(default=8, min_value=1, max_value=20)


class SmartSearchSerializer(serializers.Serializer):
    q = serializers.CharField(max_length=200)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=50)
