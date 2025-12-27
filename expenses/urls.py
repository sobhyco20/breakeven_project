from django.urls import path
from . import views, api

app_name = "expenses"

urlpatterns = [
    # Portal pages
    path("portal/definitions/", views.expenses_definitions, name="expenses_definitions"),

    # APIs
    path("portal/api/categories/list/", api.exp_categories_list, name="exp_categories_list"),
    path("portal/api/categories/", api.exp_categories_action, name="exp_categories_action"),

    path("portal/api/items/list/", api.exp_items_list, name="exp_items_list"),
    path("portal/api/items/", api.exp_items_action, name="exp_items_action"),
]
