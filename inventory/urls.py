from django.urls import path
from . import views

app_name = "inventory" 

urlpatterns = [
    path("reports/materials-period/",views.materials_period_report,name="materials_period_report",),
    path("reports/bom-tree/", views.bom_tree_report_view, name="bom_tree_report"),

]

