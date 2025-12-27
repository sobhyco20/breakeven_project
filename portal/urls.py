# portal/urls.py
from django.urls import path
from . import views, api

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("company/", views.company, name="company"),

    path("units/", views.units, name="units"),
    path("raw-materials/", views.raw_materials, name="raw_materials"),
    path("products/", views.products, name="products"),
    path("conversions/", views.unit_conversions, name="conversions"),

    # Units
    path("api/units/", api.units_api, name="units_api"),
    path("api/units/list/", api.units_list, name="units_list"),

    # Products
    path("api/products/", api.products_api, name="products_api"),
    path("api/products/list/", api.products_list, name="products_list"),

    # ✅ Raw Materials
    path("api/raw-materials/", api.raw_materials_api, name="raw_materials_api"),
    path("api/raw-materials/list/", api.raw_materials_list, name="raw_materials_list"),

        # Products
    path("products/", views.products_page, name="products_page"),
    path("api/products/list/", views.products_list, name="products_list"),
    path("api/products/", views.products_api, name="products_api"),



    path("expenses/definitions/", views.expenses_definitions, name="expenses_definitions"),

    path("api/expenses/categories/list/", api.exp_categories_list, name="exp_categories_list"),
    path("api/expenses/categories/", api.exp_categories_action, name="exp_categories_action"),
    path("api/expenses/items/list/", api.exp_items_list, name="exp_items_list"),
    path("api/expenses/items/", api.exp_items_action, name="exp_items_action"),


    path("expenses/entry/", views.expenses_entry, name="expenses_entry"),
    path("api/expenses/periods/", api.api_periods_list, name="api_periods_list"),

        # ===== Expenses Entry APIs =====
    path("api/expenses/entry/load/", api.exp_entry_load, name="exp_entry_load"),
    path("api/expenses/entry/save/", api.exp_entry_save, name="exp_entry_save"),
    path("api/expenses/entry/clear/", api.exp_entry_clear, name="exp_entry_clear"),


    path("periods/", views.periods_view, name="periods"),
    path("api/periods/list/", views.api_periods_list, name="api_periods_list"),
    path("api/periods/toggle/", views.api_periods_toggle, name="api_periods_toggle"),

    path("api/periods/list/", views.api_periods_list, name="api_periods_list"),
    path("api/periods/create/", views.api_periods_create, name="api_periods_create"),
    path("api/periods/update/", views.api_periods_update, name="api_periods_update"),
    path("api/periods/delete/", views.api_periods_delete, name="api_periods_delete"),
    path("api/periods/toggle-close/", views.api_periods_toggle_close, name="api_periods_toggle_close"),
    path("api/periods/list/", views.api_periods_list, name="api_periods_list"),
    path("api/periods/stock-toggle/", api.api_periods_stock_toggle, name="api_periods_stock_toggle"),


    
        # ===============================
    # Portal Pages
    # ===============================
    path("bom/", views.portal_bom, name="portal_bom"),
    path("bom/", views.bom, name="bom"),
    # ===============================
    # BOM APIs (Drag & Drop)
    # ===============================
    # BOM APIs (Drag & Drop)
    path("api/bom/palette/", api.bom_palette, name="api_bom_palette"),
    path("api/bom/get/<int:bom_id>/", api.bom_get, name="api_bom_get"),
    path("api/bom/save/<int:bom_id>/", api.bom_save, name="api_bom_save"),
    path("api/bom/lock-status/<int:bom_id>/", api.bom_lock_status, name="api_bom_lock_status"),

    # ✅ خلي ده هو الوحيد
    path("api/bom/open-by-product/<int:product_id>/", api.bom_open_by_product, name="api_bom_open_by_product"),

    path("api/bom/fg-products/", api.bom_fg_products, name="bom_fg_products"),


    # ✅ Inventory - StockCount Page
    path("inventory/stockcount/", views.portal_stockcount, name="portal_stockcount"),

    # ✅ Inventory APIs (StockCount)
    path("api/inventory/stockcount/state/", api.inv_stockcount_state, name="inv_stockcount_state"),
    path("api/inventory/stockcount/palette/", api.inv_stockcount_palette, name="inv_stockcount_palette"),
    path("api/inventory/units/list/", api.inv_units_list, name="inv_units_list"),

    path("api/inventory/stockcount/add-line/", api.inv_stockcount_add_line, name="inv_stockcount_add_line"),
    path("api/inventory/stockcount/update-line/", api.inv_stockcount_update_line, name="inv_stockcount_update_line"),
    path("api/inventory/stockcount/delete-line/", api.inv_stockcount_delete_line, name="inv_stockcount_delete_line"),
    path("api/inventory/stockcount/recalc/", api.inv_stockcount_recalc, name="inv_stockcount_recalc"),
    path("api/inventory/stockcount/clear-all/", api.inv_stockcount_clear_all, name="inv_stockcount_clear_all"),
    path("stockcount/", views.stockcount, name="stockcount"),
    path("api/inventory/stockcount/submit/", api.inv_stockcount_submit, name="inv_stockcount_submit"),
    
    path("sales/entry/", views.portal_sales_entry, name="portal_sales_entry"),

    # API
    path("api/sales/grid/", api.portal_sales_grid_get, name="portal_sales_grid_get"),
    path("api/sales/grid/save/", api.portal_sales_grid_save, name="portal_sales_grid_save"),
    path("sales/entry/", views.sales_entry, name="sales_entry"),



    path("purchases/entry/", views.portal_purchases_entry, name="purchases_entry"),

    # ✅ Purchases APIs
    path("api/purchases/grid/", api.portal_purchases_grid_get, name="portal_purchases_grid_get"),
    path("api/purchases/grid/save/", api.portal_purchases_grid_save, name="portal_purchases_grid_save"),






]
