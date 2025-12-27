# pricing/models.py
from decimal import Decimal
from django.db import models

from expenses.models import Period
from costing.models import Product


# =========================
# (A) تشغيل تسعير شامل للفترة
# =========================
class PricingRun(models.Model):
    period = models.ForeignKey(
        Period, on_delete=models.PROTECT,
        related_name="pricing_runs",
        verbose_name="الفترة"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    allocation_method = models.CharField(
        "طريقة توزيع المصروفات",
        max_length=30,
        choices=[
            ("by_sales_value", "حسب قيمة المبيعات"),
            ("by_qty", "حسب الكمية المباعة"),
        ],
        default="by_sales_value",
    )

    notes = models.CharField("ملاحظات", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "تشغيل تسعير"
        verbose_name_plural = "تشغيلات التسعير"
        ordering = ("-period__start_date", "-created_at")

    def __str__(self):
        return f"Pricing {self.period.start_date} ({self.get_allocation_method_display()})"


class PricingLine(models.Model):
    run = models.ForeignKey(
        PricingRun, on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="التشغيل"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="المنتج")

    qty_sold = models.DecimalField("الكمية المباعة", max_digits=18, decimal_places=4, default=Decimal("0"))
    sales_value = models.DecimalField("قيمة المبيعات", max_digits=18, decimal_places=2, default=Decimal("0"))
    avg_price = models.DecimalField("متوسط سعر البيع", max_digits=18, decimal_places=4, null=True, blank=True)

    cogs_total = models.DecimalField("إجمالي COGS", max_digits=18, decimal_places=6, default=Decimal("0"))
    cogs_unit = models.DecimalField("COGS / وحدة", max_digits=18, decimal_places=6, null=True, blank=True)

    exp_alloc_total = models.DecimalField("مصروفات موزعة", max_digits=18, decimal_places=2, default=Decimal("0"))
    exp_unit = models.DecimalField("مصروفات / وحدة", max_digits=18, decimal_places=6, null=True, blank=True)

    full_cost_unit = models.DecimalField("Full Cost / وحدة", max_digits=18, decimal_places=6, null=True, blank=True)

    profit_total = models.DecimalField("ربح إجمالي", max_digits=18, decimal_places=2, default=Decimal("0"))
    profit_unit = models.DecimalField("ربح / وحدة", max_digits=18, decimal_places=6, null=True, blank=True)
    margin_pct = models.DecimalField("Margin %", max_digits=9, decimal_places=2, null=True, blank=True)

    suggested_price = models.DecimalField("سعر مقترح", max_digits=18, decimal_places=4, null=True, blank=True)
    target_margin_pct = models.DecimalField("هامش مستهدف %", max_digits=9, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "نتيجة تسعير"
        verbose_name_plural = "نتائج التسعير"
        unique_together = ("run", "product")
        ordering = ("-profit_total",)

    def __str__(self):
        return f"{self.product.code} ({self.run})"


# =========================
# (B) سياسة تسعير لمنتج محدد (أبسط)
# =========================
class PricingPolicy(models.Model):
    PRICING_METHODS = [
        ("margin_percent", "نسبة ربح %"),
        ("margin_amount", "مبلغ ربح ثابت"),
        ("manual_price", "سعر بيع يدوي"),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="المنتج",
        limit_choices_to={"is_sellable": True, "is_semi_finished": False},
    )

    period = models.ForeignKey(Period, on_delete=models.CASCADE, verbose_name="الفترة")

    pricing_method = models.CharField(
        max_length=20,
        choices=PRICING_METHODS,
        default="margin_percent",
        verbose_name="طريقة التسعير",
    )

    margin_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"), verbose_name="نسبة الربح %")
    margin_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"), verbose_name="مبلغ الربح")
    manual_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"), verbose_name="سعر البيع اليدوي")

    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    is_active = models.BooleanField(default=True, verbose_name="نشط")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "period")
        verbose_name = "سياسة تسعير"
        verbose_name_plural = "سياسات التسعير"

    def __str__(self):
        return f"{self.product} – {self.period}"


class PricingResult(models.Model):
    pricing_policy = models.OneToOneField(PricingPolicy, on_delete=models.CASCADE, related_name="result")

    cost_per_unit = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="تكلفة الوحدة")
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="سعر البيع")
    gross_profit = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="مجمل الربح")
    gross_margin_percent = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="نسبة مجمل الربح %")

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "نتيجة سياسة التسعير"
        verbose_name_plural = "نتائج سياسات التسعير"

# pricing/models.py
class PricingContext(models.Model):
    period = models.ForeignKey("expenses.Period", on_delete=models.CASCADE)
    product = models.ForeignKey("costing.Product", on_delete=models.CASCADE)

    direct_cost = models.DecimalField(max_digits=14, decimal_places=4)
    allocated_expense = models.DecimalField(max_digits=14, decimal_places=4)

    full_cost = models.DecimalField(max_digits=14, decimal_places=4)

    sales_qty = models.DecimalField(max_digits=14, decimal_places=4)
    sales_value = models.DecimalField(max_digits=14, decimal_places=4)

    contribution = models.DecimalField(max_digits=14, decimal_places=4)
