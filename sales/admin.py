# sales/admin.py
from decimal import Decimal
from django.db.models import Sum
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
import pandas as pd

from decimal import Decimal, ROUND_HALF_UP

def round3(value):
    if value is None:
        return None
    return Decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


from .models import SalesSummary, SalesSummaryLine,SalesConsumption
from .forms import SalesSummaryImportForm
from costing.models import Product, Unit

from django.contrib import admin, messages
from .models import SalesConsumptionSummary, SalesConsumption, generate_sales_consumption

class SalesSummaryLineInline(admin.TabularInline):
    model = SalesSummaryLine
    extra = 1
    autocomplete_fields = ("product", "unit")
    fields = ("product", "unit", "quantity", "unit_price", "line_total")
    readonly_fields = ("line_total",)


@admin.register(SalesSummary)
class SalesSummaryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "period", "display_total_amount")
    inlines = [SalesSummaryLineInline]

    readonly_fields = ("display_total_amount",)
    fields = ("period", "display_total_amount")

    change_list_template = "admin/sales/salessummary_changelist.html"

    def display_total_amount(self, obj):
        return obj.total_amount()
    display_total_amount.short_description = "إجمالي قيمة المبيعات"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="sales_salessummary_import_excel",
            ),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        if request.method == "POST":
            form = SalesSummaryImportForm(request.POST, request.FILES)
            if form.is_valid():
                period = form.cleaned_data["period"]
                excel_file = form.cleaned_data["excel_file"]

                try:
                    df = pd.read_excel(excel_file)
                    cols = {str(c).strip(): c for c in df.columns}

                    name_col = cols.get("المنتج")
                    code_col = cols.get("كود تعريف المنتج")
                    qty_col = cols.get("صافي الكمية")
                    unit_price_col = cols.get("سعر الوحدة")
                    line_total_col = cols.get("إجمالي المبيعات")

                    if not (name_col and qty_col and unit_price_col):
                        messages.error(
                            request,
                            "تأكد أن ملف الإكسل يحتوي الأعمدة: المنتج، صافي الكمية، سعر الوحدة (وإجمالي المبيعات اختياري).",
                        )
                        return redirect("admin:sales_salessummary_changelist")

                    summary = SalesSummary.objects.create(
                        period=period,
                    )

                    for _, row in df.iterrows():
                        name = ""
                        code = ""

                        if name_col and not pd.isna(row[name_col]):
                            name = str(row[name_col]).strip()
                        if code_col and not pd.isna(row[code_col]):
                            code = str(row[code_col]).strip()

                        if not name and not code:
                            continue

                        product = None
                        if code:
                            product = Product.objects.filter(code=code).first()
                        if not product and name:
                            product = Product.objects.filter(name=name).first()
                        if not product:
                            continue

                        unit = product.base_unit
                        if not unit:
                            unit, _ = Unit.objects.get_or_create(
                                name="وحدة",
                                defaults={"abbreviation": "وحدة"},
                            )

                        qty = Decimal(str(row[qty_col])) if not pd.isna(row[qty_col]) else Decimal("0")
                        unit_price = (
                            Decimal(str(row[unit_price_col]))
                            if not pd.isna(row[unit_price_col])
                            else Decimal("0")
                        )

                        if line_total_col and not pd.isna(row[line_total_col]):
                            line_total = Decimal(str(row[line_total_col]))
                        else:
                            line_total = qty * unit_price

                        SalesSummaryLine.objects.create(
                            summary=summary,
                            product=product,
                            unit=unit,
                            quantity=qty,
                            unit_price=unit_price,
                            line_total=line_total,
                        )

                    messages.success(request, "تم استيراد ملخص المبيعات من ملف الإكسل بنجاح.")
                    return redirect("admin:sales_salessummary_change", summary.pk)

                except Exception as e:
                    messages.error(request, f"حدث خطأ أثناء قراءة الملف: {e}")
        else:
            form = SalesSummaryImportForm()

        context = {
            "form": form,
            "title": "استيراد ملخص المبيعات من إكسل",
        }
        return render(request, "admin/sales/salessummary_import.html", context)


class SalesConsumptionInline(admin.TabularInline):
    model = SalesConsumption
    extra = 0
    can_delete = False

    fields = (
        "product",
        "raw_material",
        "source_type",
        "source_product",
        "level",
        "quantity_sold",
        "quantity_consumed",           # بوحدة الاستخدام
        "quantity_consumed_storage_display",  # بوحدة التخزين
        "unit_cost",
        "total_cost",
    )

    readonly_fields = fields

    def quantity_consumed_storage_display(self, obj):
        return obj.quantity_consumed_storage()
    quantity_consumed_storage_display.short_description = "الكمية بوحدة التخزين"



@admin.register(SalesConsumptionSummary)
class SalesConsumptionSummaryAdmin(admin.ModelAdmin):
    list_display = ("period", "total_quantity_consumed", "total_cost_consumed")
    search_fields = ("period__name",)
    inlines = [SalesConsumptionInline]

    actions = ["regenerate_consumption"]

        # إجمالي الكميات لهذا الشهر
    def total_quantity_consumed(self, obj):
        total = obj.lines.aggregate(total=Sum("quantity_consumed"))["total"] or 0
        return round3(total)
    total_quantity_consumed.short_description = "إجمالي الكمية المستهلكة"

        # إجمالي التكلفة لهذا الشهر
    def total_cost_consumed(self, obj):
        total = obj.lines.aggregate(total=Sum("total_cost"))["total"] or 0
        return round3(total)
    total_cost_consumed.short_description = "إجمالي تكلفة الاستهلاك"

    # زر / أكشن لإعادة التوليد من المبيعات و الـ BOM
    def regenerate_consumption(self, request, queryset):
        count = 0
        for summary in queryset:
            # نحذف القديم ونولّد من جديد
            generate_sales_consumption(summary.period)
            count += 1

        self.message_user(
            request,
            f"تم إعادة توليد استهلاك المواد لـ {count} فترة.",
            level=messages.SUCCESS,
        )

    regenerate_consumption.short_description = "إعادة توليد استهلاك المواد للفترات المختارة"