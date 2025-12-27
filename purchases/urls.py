# purchases/urls.py
from django.urls import path
from .views import purchase_price_comparison_view

urlpatterns = [
    # ... روابط أخرى
    path(
        "reports/purchase-price-comparison/",
        purchase_price_comparison_view,
        name="purchase_price_comparison"
    ),
]
