from django.urls import path
from .views import pricing_dashboard, pricing_product
from .api import (
    pricing_dashboard_data,
    pricing_product_calc,
    pricing_product_pnl,
    pricing_save_scenario,
    pricing_load_scenario,
)

urlpatterns = [
    path("dashboard/", pricing_dashboard, name="pricing_dashboard"),

    # ✅ NEW: صفحة تسعير منتج واحد داخل iframe
    path("product/", pricing_product, name="pricing_product"),

    path("api/dashboard-data/", pricing_dashboard_data, name="pricing_dashboard_data"),
    path("api/product-calc/", pricing_product_calc, name="pricing_product_calc"),
    path("api/product-pnl/", pricing_product_pnl, name="pricing_product_pnl"),
    path("api/scenario/save/", pricing_save_scenario, name="pricing_save_scenario"),
    path("api/scenario/load/<int:scenario_id>/", pricing_load_scenario, name="pricing_load_scenario"),
]
