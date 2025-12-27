# pricing/admin.py
from decimal import Decimal

from django.contrib import admin, messages
from django.db.models import Sum
from django.shortcuts import redirect
from django.urls import path

from expenses.models import Period

from .models import PricingRun, PricingLine, PricingPolicy, PricingResult

from .services.pricing_engine import calculate_price
from decimal import Decimal
from django.contrib import admin

from .models import PricingPolicy, PricingResult
from .services.pricing_engine import calculate_price
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import redirect
from django.utils.html import format_html
from decimal import Decimal

# =========================
# (A) Admin: PricingRun / PricingLine
# =========================
class PricingLineInline(admin.TabularInline):
    model = PricingLine
    extra = 0
    can_delete = False
    readonly_fields = (
        "product", "qty_sold", "sales_value", "avg_price",
        "cogs_total", "cogs_unit",
        "exp_alloc_total", "exp_unit",
        "full_cost_unit",
        "profit_total", "profit_unit", "margin_pct",
        "target_margin_pct", "suggested_price",
    )
    fields = readonly_fields


@admin.register(PricingRun)
class PricingRunAdmin(admin.ModelAdmin):
    list_display = ("period", "allocation_method", "created_at", "totals")
    list_filter = ("allocation_method", "period__year", "period__month")
    search_fields = ("period__start_date",)
    inlines = [PricingLineInline]

    def totals(self, obj):
        t_sales = obj.lines.aggregate(t=Sum("sales_value"))["t"] or 0
        t_profit = obj.lines.aggregate(t=Sum("profit_total"))["t"] or 0
        return f"Sales={t_sales} | Profit={t_profit}"
    totals.short_description = "إجمالي"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "run/<int:period_id>/",
                self.admin_site.admin_view(self.run_for_period),
                name="pricing_run_for_period",
            ),
        ]
        return custom + urls

    def run_for_period(self, request, period_id):
        period = Period.objects.filter(id=period_id).first()
        if not period:
            messages.error(request, "الفترة غير موجودة")
            return redirect("..")

        # ⚠️ ملاحظة:
        # أنت مستدعي run_pricing هنا على أساس أنه يشغّل PricingRun للفترة.
        # بينما run_pricing في services/run_pricing.py يخص PricingPolicy فقط.
        # لذا: لو هدفك تشغيل PricingRun الحقيقي، لازم يكون عندك دالة مختلفة (run_pricing_run).
        messages.warning(
            request,
            "ملاحظة: زر التشغيل الحالي مرتبط بسياسة التسعير PricingPolicy وليس PricingRun. "
            "لو تريد تشغيل PricingRun للفترة سنبني run_pricing_run في الخطوة القادمة."
        )
        return redirect("..")


@admin.register(PricingLine)
class PricingLineAdmin(admin.ModelAdmin):
    list_display = ("run", "product", "qty_sold", "sales_value", "full_cost_unit", "profit_total", "margin_pct", "suggested_price")
    list_filter = ("run__period__year", "run__period__month", "run__allocation_method")
    search_fields = ("product__code", "product__name")


# =========================
# (B) Admin: PricingPolicy / PricingResult
# =========================
class PricingResultInline(admin.StackedInline):
    model = PricingResult
    can_delete = False
    extra = 0
    readonly_fields = (
        "cost_per_unit",
        "selling_price",
        "gross_profit",
        "gross_margin_percent",
        "calculated_at",
    )

@admin.register(PricingPolicy)
class PricingPolicyAdmin(admin.ModelAdmin):
    list_display = ("product", "period", "pricing_method", "is_active")
    list_filter = ("period", "pricing_method", "is_active")
    search_fields = ("product__name", "product__code")

    # ✅ يظهر داخل صفحة السجل
    readonly_fields = ("recalc_button",)

    inlines = []  # لو عندك inline للـ PricingResult سيبها زي ما هي

    def recalc_button(self, obj):
        if not obj or not obj.pk:
            return ""
        url = reverse("admin:pricing_pricingpolicy_recalc", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="padding:6px 12px;">🔁 إعادة احتساب</a>',
            url
        )
    recalc_button.short_description = "إعادة احتساب"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:policy_id>/recalc/",
                self.admin_site.admin_view(self.recalc_view),
                name="pricing_pricingpolicy_recalc",
            )
        ]
        return custom + urls

    def recalc_view(self, request, policy_id):
        policy = PricingPolicy.objects.select_related("product", "period").filter(pk=policy_id).first()
        if not policy:
            messages.error(request, "السياسة غير موجودة.")
            return redirect("..")

        # ✅ 1) احسب تكلفة الوحدة
        cost_per_unit = policy.product.compute_unit_cost(period=policy.period) or Decimal("0")

        # ✅ 2) احسب السعر والربح حسب السياسة
        result = calculate_price(cost_per_unit, policy)

        # ✅ 3) خزّن النتيجة
        PricingResult.objects.update_or_create(
            pricing_policy=policy,
            defaults={"cost_per_unit": cost_per_unit, **result},
        )

        messages.success(
            request,
            f"تمت إعادة الاحتساب بنجاح ✅ | تكلفة الوحدة: {cost_per_unit} | سعر البيع: {result.get('selling_price')}"
        )

        # رجوع لصفحة السجل
        return redirect(
            reverse("admin:pricing_pricingpolicy_change", args=[policy.pk])
        )
