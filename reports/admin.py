# reports/admin.py
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import InventoryReports


@admin.register(InventoryReports)
class InventoryReportsAdmin(admin.ModelAdmin):
    # نمنع الإضافة / الحذف / التعديل
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        # ما نحتاج نموذج تفاصيل، فقط نستخدم قائمة الموديل
        return True

    # عند فتح قائمة الموديل → نعيد توجيه المستخدم لصفحة التقارير الرئيسية
    def changelist_view(self, request, extra_context=None):
        return redirect(reverse("reports_home"))
