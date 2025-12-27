# purchases/models.py
from django.db import models
from decimal import Decimal
from costing.models import RawMaterial, Unit
from expenses.models import Period


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("تاريخ آخر تعديل", auto_now=True)

    class Meta:
        abstract = True


class PurchaseSummary(models.Model):
    period = models.ForeignKey(
        Period,
        on_delete=models.PROTECT,
        related_name="purchase_summaries",
        verbose_name="الفترة",
        null=True,
        blank=True,
    )
    total_amount = models.DecimalField(
        "إجمالي قيمة المشتريات",
        max_digits=18, decimal_places=2,
        default=0,
    )

    class Meta:
        verbose_name = "ملخص مشتريات"
        verbose_name_plural = "ملخصات المشتريات"

    def __str__(self):
        return f"مشتريات - {self.period}"

    def recalculate_totals(self):
        total = Decimal("0")
        for line in self.lines.all():
            if line.line_total is not None:
                total += line.line_total
        self.total_amount = total
        self.save(update_fields=["total_amount"])



from decimal import Decimal
from django.db import models

class PurchaseSummaryLine(models.Model):
    summary = models.ForeignKey("purchases.PurchaseSummary", related_name="lines",
                                on_delete=models.CASCADE, verbose_name="الملخّص")
    raw_material = models.ForeignKey("costing.RawMaterial", on_delete=models.PROTECT, verbose_name="المادة الخام")
    purchase_unit = models.ForeignKey("costing.Unit", on_delete=models.PROTECT, verbose_name="وحدة الشراء")

    quantity = models.DecimalField("إجمالي الكمية المشتراة", max_digits=18, decimal_places=4, default=0)
    unit_cost = models.DecimalField("تكلفة الشراء للوحدة", max_digits=18, decimal_places=6, default=0)

    line_total = models.DecimalField("إجمالي الصنف", max_digits=18, decimal_places=2, editable=False, default=0)
    last_unit_cost = models.DecimalField("آخر تكلفة", max_digits=18, decimal_places=2, default=0)


    class Meta:
        verbose_name = "سطر ملخص مشتريات"
        verbose_name_plural = "سطور ملخص المشتريات"

    def __str__(self):
        return f"{self.raw_material} - {self.summary}"

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or Decimal("0")) * (self.unit_cost or Decimal("0"))
        super().save(*args, **kwargs)
        if hasattr(self.summary, "recalculate_totals"):
            self.summary.recalculate_totals()
