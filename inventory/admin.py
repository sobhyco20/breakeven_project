from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django.http import HttpResponse
from decimal import Decimal
import pandas as pd

from django.urls import reverse
from django.utils.html import format_html


from .models import (
    StockCount,
    StockCountLine,
    InventoryIssue,
    InventoryIssueLine,
)
from .forms import StockCountImportForm
from costing.models import RawMaterial, Product, Unit


class StockCountLineInline(admin.TabularInline):
    model = StockCountLine
    extra = 0
    readonly_fields = ("saved_unit_cost", "saved_total_cost")
    fields = (
        "raw_material",
        "semi_finished_product",
        "unit",
        "quantity",
        "saved_unit_cost",
        "saved_total_cost",
    )


    def unit_cost_display(self, obj):
        return obj.unit_cost_value
    unit_cost_display.short_description = "تكلفة الوحدة"

    def line_total_cost_display(self, obj):
        return obj.line_total_value
    line_total_cost_display.short_description = "إجمالي تكلفة البند"


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('raw_material', 'semi_finished_product', 'unit', 'stock_count')



@admin.register(StockCount)
class StockCountAdmin(admin.ModelAdmin):
    list_display = ("period", "count_type", "total_quantity_display", "total_cost_display")
    list_filter = ["type"]
    inlines = [StockCountLineInline]
    readonly_fields = ("total_cost_display",)
    fields = ("period", "count_type", "count_date", "notes", "total_cost_display")


    

    def total_quantity_display(self, obj):
        return obj.total_quantity()
    total_quantity_display.short_description = "إجمالي الكمية"

    def total_cost_display(self, obj):
        return obj.total_cost()
    total_cost_display.short_description = "إجمالي تكلفة الجرد"

    @admin.action(description="🔄 تحديث التكاليف المحفوظة")
    def update_costs(self, request, queryset):
        updated = 0
        for stock_count in queryset:
            for line in stock_count.lines.all():
                line.save()  # يحفظ التكلفة الجديدة
                updated += 1
        self.message_user(request, f"تم تحديث التكاليف لـ {updated} بند.", level=messages.SUCCESS)

    actions = [update_costs]


    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="inventory_stockcount_import_excel",
            ),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        """
        استيراد الجرد من ملف إكسل:
        الأعمدة المتوقعة (على الأقل):
        - كود المادة
        - اسم المادة (اختياري)
        - الوحدة
        - الكمية
        """
        if request.method == "POST":
            form = StockCountImportForm(request.POST, request.FILES)
            if form.is_valid():
                period = form.cleaned_data["period"]
                count_type = form.cleaned_data["count_type"]
                count_date = form.cleaned_data["count_date"]
                excel_file = form.cleaned_data["excel_file"]

                try:
                    df = pd.read_excel(excel_file)
                    cols = {c.strip(): c for c in df.columns}

                    code_col = cols.get("كود المادة") or cols.get("code") or cols.get("sku")
                    name_col = cols.get("اسم المادة") or cols.get("name")
                    unit_col = cols.get("الوحدة") or cols.get("unit")
                    qty_col = cols.get("الكمية") or cols.get("quantity")

                    if not (code_col and unit_col and qty_col):
                        messages.error(
                            request,
                            "تأكد أن ملف الإكسل يحتوي الأعمدة: كود المادة، الوحدة، الكمية "
                            "(يمكن إضافة 'اسم المادة' كعمود اختياري).",
                        )
                        return redirect("admin:inventory_stockcount_changelist")

                    # إنشاء رأس الجرد
                    stock_count = StockCount.objects.create(
                        period=period,
                        count_type=count_type,
                        count_date=count_date,
                    )

                    for _, row in df.iterrows():
                        if all(pd.isna(v) for v in row):
                            continue

                        code = str(row[code_col]).strip() if not pd.isna(row[code_col]) else ""
                        if not code:
                            continue

                        name_val = ""
                        if name_col and not pd.isna(row[name_col]):
                            name_val = str(row[name_col]).strip()

                        unit_name = str(row[unit_col]).strip() if not pd.isna(row[unit_col]) else ""
                        qty_val = row[qty_col]

                        if not unit_name or pd.isna(qty_val):
                            continue

                        # البحث أولاً في المواد الخام بالكود
                        raw = RawMaterial.objects.filter(sku=code).first()
                        semi_finished = None

                        # لو مش مادة خام، نجرب كمنتج نصف مصنع
                        if not raw:
                            semi_finished = Product.objects.filter(code=code, is_semi_finished=True).first()

                        # لو لا خام ولا نصف مصنع → نتجاهل
                        if not raw and not semi_finished:
                            continue

                        unit, _ = Unit.objects.get_or_create(
                            name=unit_name,
                            defaults={"abbreviation": unit_name},
                        )

                        try:
                            quantity = Decimal(str(qty_val))
                        except Exception:
                            continue

                        StockCountLine.objects.create(
                            stock_count=stock_count,
                            raw_material=raw,
                            semi_finished_product=semi_finished,
                            unit=unit,
                            quantity=quantity,
                        )

                    messages.success(request, "تم استيراد الجرد من ملف الإكسل بنجاح.")
                    return redirect("admin:inventory_stockcount_changelist")

                except Exception as e:
                    messages.error(request, f"حدث خطأ أثناء قراءة الملف: {e}")
                    return redirect("admin:inventory_stockcount_changelist")
        else:
            form = StockCountImportForm()

        context = {
            "form": form,
            "title": "استيراد جرد المستودع من إكسل",
        }
        return render(request, "admin/inventory/stockcount_import.html", context)
    

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import BomTreeReport


@admin.register(BomTreeReport)
class BomTreeReportAdmin(admin.ModelAdmin):
    list_display = ()  # لا نعرض أعمدة

    # منع الإضافة / التعديل / الحذف
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # عند فتح "قائمة" هذا الموديل -> نحول مباشرة لصفحة التقرير
    def changelist_view(self, request, extra_context=None):
        url = reverse("inventory:bom_tree_report")  # نفس اسم الـ URL الذي استخدمناه
        return redirect(url)
