# reports/urls.py
from django.urls import path
from . import views
from .views import product_cost_breakdown,product_cost_flat,product_cost_with_big_units,product_cost_with_big_units_all_pdf,product_cost_with_big_units_pdf
from .views import income_statement_drilldown

urlpatterns = [
    path("", views.reports_home, name="reports_home"),

    path(
        "raw-material-consumption/summary/",
        views.raw_material_consumption_summary,
        name="raw_material_consumption_summary",
    ),
    path(
        "raw-material-consumption/detail/",
        views.raw_material_consumption_detail,
        name="raw_material_consumption_detail",
    ),

        path(
        "raw-material-usage/by-product/",
        views.raw_material_usage_by_product,
        name="raw_material_usage_by_product",
    ),

    path(
    "raw-material-consumption-with-manufactured/",
    views.raw_material_consumption_with_manufactured_detail,
    name="raw_material_consumption_with_manufactured_detail",
),

    path(
        "product-cost-breakdown/",
        product_cost_breakdown,
        name="product_cost_breakdown",
    ),

    
    path("product-cost-breakdown/", views.product_cost_breakdown, name="product_cost_breakdown"),
    path("product-cost/pdf/", views.product_cost_breakdown_pdf, name="product_cost_breakdown_pdf"),
    path("product-cost/pdf/all/", views.product_cost_breakdown_all_pdf, name="product_cost_breakdown_all_pdf"),
    path("product-cost-flat/", product_cost_flat, name="product_cost_flat"),

        path(
        "product-cost-with-big-units/",
        product_cost_with_big_units,
        name="product_cost_with_big_units",
    ),

    path(
        "product-cost-with-big-units/pdf/",
        product_cost_with_big_units_pdf,
        name="product_cost_with_big_units_pdf",
    ),
    path(
        "product-cost-with-big-units/pdf/all/",
        product_cost_with_big_units_all_pdf,
        name="product_cost_with_big_units_all_pdf",
    ),


    path(
        "income-statement/",
        views.income_statement,
        name="income_statement",
    ),

    path("income-statement-drilldown/", income_statement_drilldown, name="income_statement_drilldown"),
]
