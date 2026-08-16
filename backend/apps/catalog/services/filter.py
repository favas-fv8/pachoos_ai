"""Catalog services — search and filter logic."""
import re
from typing import Any

from django.db import models
from django.db.models import Q, QuerySet

from apps.catalog.models import Category


def apply_search(queryset: QuerySet, query: str) -> QuerySet:
    if not query:
        return queryset

    raw = query.strip()
    lower = raw.lower()
    tokens = re.findall(r"[\w]+", lower)

    if not tokens:
        return queryset

    # Build AND query: every token must match at least one searchable field
    and_q = Q()
    for token in tokens:
        token_q = (
            Q(name__icontains=token)
            | Q(description__icontains=token)
            | Q(brand__icontains=token)
            | Q(sku__icontains=token)
            | Q(product_tags__tag__name__icontains=token)
            | Q(subcategory__name__icontains=token)
            | Q(subcategory__category__name__icontains=token)
        )
        and_q &= token_q

    return queryset.filter(and_q).distinct()


def apply_filters(
    queryset: QuerySet,
    category: str | None = None,
    subcategory: str | None = None,
    freshness: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    sort_by: str = "popularity",
    available_only: bool = False,
) -> QuerySet:
    if category:
        queryset = queryset.filter(
            subcategory__category__slug=category
        )
    if subcategory:
        queryset = queryset.filter(subcategory__slug=subcategory)
    if freshness:
        queryset = queryset.filter(freshness=freshness)
    if min_price is not None:
        queryset = queryset.filter(base_price__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(base_price__lte=max_price)
    if min_rating is not None:
        queryset = queryset.filter(avg_rating__gte=min_rating)
    if available_only:
        queryset = queryset.filter(is_available=True, stock_quantity__gt=0)

    # Sorting
    sort_map: dict[str, str] = {
        "popularity": "-times_sold",
        "newest": "-created_at",
        "price_asc": "base_price",
        "price_desc": "-base_price",
        "discount": "-discount_percent",
        "rating": "-avg_rating",
        "name": "name",
    }
    ordering = sort_map.get(sort_by, "-times_sold")
    queryset = queryset.order_by(ordering)

    return queryset


def get_filter_options(queryset: QuerySet) -> dict[str, Any]:
    """Return distinct filter values for the current queryset."""
    return {
        "categories": list(
            Category.objects.filter(is_active=True).values("id", "name", "slug")
        ),
        "freshness_values": [
            {"value": "fresh", "label": "Fresh"},
            {"value": "frozen", "label": "Frozen"},
            {"value": "bakery", "label": "Bakery"},
            {"value": "dry", "label": "Dry"},
        ],
        "price_range": {
            "min": float(queryset.aggregate(min_price=models.Min("base_price"))["min_price"] or 0),
            "max": float(queryset.aggregate(max_price=models.Max("base_price"))["max_price"] or 0),
        },
    }
