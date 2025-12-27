# purchases/admin.py
from decimal import Decimal

from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
import pandas as pd

from .models import PurchaseSummary, PurchaseSummaryLine
from .forms import PurchaseSummaryImportForm
from costing.models import RawMaterial, Unit


class PurchaseSummaryLineInline(admin.TabularInline):
    model = PurchaseSummaryLine
    extra = 1
    autocomplete_fields = ("raw_material", "purchase_unit")
    fields = ("raw_material", "purchase_unit", "quantity", "unit_cost", "line_total")
    readonly_fields = ("line_total",)

@admin.register(PurchaseSummary)
class PurchaseSummaryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "period", "display_total_amount")
    inlines = [PurchaseSummaryLineInline]

    readonly_fields = ("display_total_amount",)
    fields = ("period", "total_amount", "display_total_amount")
    change_list_template = "admin/purchases/purchasesummary_changelist.html"

    def display_total_amount(self, obj):
        return obj.total_amount
    display_total_amount.short_description = "إجمالي قيمة المشتريات"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="purchases_purchasesummary_import_excel",
            ),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        if request.method == "POST":
            form = PurchaseSummaryImportForm(request.POST, request.FILES)
            if form.is_valid():
                period = form.cleaned_data["period"]
                excel_file = form.cleaned_data["excel_file"]

                try:
                    df = pd.read_excel(excel_file)

                    cols = {c.strip(): c for c in df.columns}

                    sku_col = cols.get("كود") or cols.get("code") or cols.get("SKU")
                    name_col = cols.get("اسم المادة")
                    unit_col = cols.get("وحدة الشراء")
                    qty_col = cols.get("الكمية")
                    unit_cost_col = cols.get("تكلفة الشراء للوحدة")
                    line_total_col = cols.get("إجمالي الصنف")

                    if not (sku_col and unit_col and qty_col and unit_cost_col):
                        messages.error(
                            request,
                            "تأكد أن ملف الإكسل يحتوي الأعمدة: كود، وحدة الشراء، الكمية، تكلفة الشراء للوحدة."
                        )
                        return redirect("admin:purchases_purchasesummary_changelist")

                    summary = PurchaseSummary.objects.create(
                        period=period,
                        total_amount=0
                    )

                    from decimal import Decimal

                    for _, row in df.iterrows():
                        sku = str(row[sku_col]).strip()
                        if not sku:
                            continue

                        raw = RawMaterial.objects.filter(sku=sku).first()

                        if not raw and name_col:
                            name = str(row[name_col]).strip()
                            if name:
                                raw = RawMaterial.objects.filter(name=name).first()

                        if not raw:
                            continue

                        unit_name = str(row[unit_col]).strip()
                        purchase_unit, _ = Unit.objects.get_or_create(
                            name=unit_name or "وحدة",
                            defaults={"abbreviation": unit_name or "وحدة"},
                        )

                        qty = Decimal(str(row[qty_col])) if not pd.isna(row[qty_col]) else Decimal("0")
                        unit_cost = Decimal(str(row[unit_cost_col])) if not pd.isna(row[unit_cost_col]) else Decimal("0")

                        if line_total_col and not pd.isna(row[line_total_col]):
                            line_total = Decimal(str(row[line_total_col]))
                        else:
                            line_total = qty * unit_cost

                        PurchaseSummaryLine.objects.create(
                            summary=summary,
                            raw_material=raw,
                            purchase_unit=purchase_unit,
                            quantity=qty,
                            unit_cost=unit_cost,
                            line_total=line_total,
                        )

                        # تحديث تكلفة المادة الخام من آخر تكلفة شراء
                        raw.purchase_price_per_storage_unit = unit_cost
                        raw.update_cost_per_ingredient_unit()
                        raw.save()

                    # تحديث إجمالي الملخص
                    summary.recalculate_totals()

                    messages.success(request, "تم استيراد ملخص المشتريات من ملف الإكسل بنجاح.")
                    return redirect("admin:purchases_purchasesummary_change", summary.pk)

                except Exception as e:
                    messages.error(request, f"حدث خطأ أثناء قراءة الملف: {e}")
                    return redirect("admin:purchases_purchasesummary_changelist")
        else:
            form = PurchaseSummaryImportForm()

        context = {
            "form": form,
            "title": "استيراد ملخص المشتريات من إكسل",
        }
        return render(request, "admin/purchases/purchasesummary_import.html", context)
