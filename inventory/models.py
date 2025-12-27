from django.db import models
from decimal import Decimal
from costing.models import RawMaterial, Product, Unit
from expenses.models import Period
from decimal import Decimal
from costing.models import round3
from functools import cached_property
from django.db.models import Q, CheckConstraint
from django.core.exceptions import ValidationError
from django.utils import timezone

from decimal import Decimal, ROUND_HALF_UP

def round3(value):
    """تقريب إلى 3 منازل عشرية مع دعم None."""
    if value is None:
        return None
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.000"), rounding=ROUND_HALF_UP)




class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ آخر تعديل")

    class Meta:
        abstract = True


class StockCountType(models.TextChoices):
    OPENING = "OPENING", "جرد أول الفترة"
    CLOSING = "CLOSING", "جرد آخر الفترة"
    INTERIM = "INTERIM", "جرد وسيط"


class StockCount(TimeStampedModel):
    """رأس جرد المستودع لفترة معيّنة (أول / آخر الفترة)."""

    count_date = models.DateField("تاريخ الجرد")
    notes = models.CharField("ملاحظات", max_length=30, blank=True, null=True)

    TYPE_CHOICES = (
        ("opening", "جرد أول الفترة"),
        ("closing", "جرد آخر الفترة"),
    )

    period = models.ForeignKey(Period, on_delete=models.PROTECT, verbose_name="الفترة")

    type = models.CharField("نوع الجرد", max_length=20, choices=TYPE_CHOICES)
    count_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="opening")  # اتركه لو تستخدمه
    is_committed = models.BooleanField("تم اعتماد الجرد", default=False)
    committed_at = models.DateTimeField("تاريخ الاعتماد", null=True, blank=True)

    def commit(self):
        if not self.is_committed:
            self.is_committed = True
            self.committed_at = timezone.now()
            self.save(update_fields=["is_committed", "committed_at"])


    class Meta:
        verbose_name = "جرد مستودع"
        verbose_name_plural = "جرد المستودع"
        unique_together = ("period", "type")

    def __str__(self):
        return f"{self.get_type_display()} - {self.period}"

    def total_quantity(self):
        total = Decimal("0")
        for line in self.lines.all():
            total += (line.quantity or Decimal("0"))
        return round3(total)

    def total_cost(self):
        total = Decimal("0")
        for line in self.lines.all():
            line_cost = line.line_total_cost()
            if line_cost is not None:
                total += line_cost
        return round3(total)


class StockCountLine(TimeStampedModel):
    """بنود الجرد (مادة خام أو منتج نصف مصنع)."""

    stock_count = models.ForeignKey(
        StockCount,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="الجرد",
    )

    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="مادة خام",
    )

    semi_finished_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="منتج نصف مصنع",
        help_text="منتج مكوّن يستخدم في الوصفات",
    )

    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, verbose_name="وحدة الجرد")

    # ✅ الأفضل default=0 عشان prefill
    quantity = models.DecimalField("الكمية المجردة", max_digits=16, decimal_places=4, default=Decimal("0"))

    # ✅ تكلفة يدوية (Opening فقط)
    unit_cost_value = models.DecimalField(
        "تكلفة الوحدة اليدوية (Opening)",
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
    )

    saved_unit_cost = models.DecimalField(
        "تكلفة الوحدة المحفوظة",
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
    )

    saved_total_cost = models.DecimalField(
        "إجمالي تكلفة البند المحفوظة",
        max_digits=16,
        decimal_places=4,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "بند جرد"
        verbose_name_plural = "بنود الجرد"
        constraints = [
            # ✅ لازم يكون أحدهما فقط موجود
            CheckConstraint(
                name="stockcountline_exactly_one_item",
                check=(
                    # (raw is not null AND semi is null) OR (raw is null AND semi is not null)
                    (Q(raw_material__isnull=False) & Q(semi_finished_product__isnull=True))
                    | (Q(raw_material__isnull=True) & Q(semi_finished_product__isnull=False))
                ),
            ),
        ]

    def __str__(self):
        item = self.raw_material or self.semi_finished_product
        return f"{item} - {self.quantity} {self.unit}"

    def clean(self):
        # حماية إضافية (خاصة قبل constraints أو أثناء admin forms)
        if bool(self.raw_material_id) == bool(self.semi_finished_product_id):
            raise ValidationError("يجب اختيار مادة خام أو نصف مصنع (واحد فقط).")

        if self.quantity is not None and self.quantity < 0:
            raise ValidationError("الكمية لا يمكن أن تكون سالبة.")

        if self.unit_cost_value is not None and self.unit_cost_value < 0:
            raise ValidationError("التكلفة لا يمكن أن تكون سالبة.")

        # ✅ لو Closing: ممنوع إدخال تكلفة يدوية
        if self.stock_count_id and self.stock_count.type == "closing" and self.unit_cost_value is not None:
            raise ValidationError("تكلفة الوحدة اليدوية مسموحة في جرد أول الفترة فقط.")

    def save(self, *args, **kwargs):
        # ✅ شغّل clean (خصوصًا مع bulk_create لن يعمل تلقائيًا، لكن في التعديلات العادية نعم)
        if kwargs.pop("validate", True):
            try:
                self.full_clean()
            except Exception:
                # لو لا تريد كسر عمليات داخلية، احذف try/except
                raise

        # ✅ Opening + تكلفة يدوية => نعتمدها
        if self.stock_count_id and self.stock_count.type == "opening" and self.unit_cost_value is not None:
            self.saved_unit_cost = round3(self.unit_cost_value)
            self.saved_total_cost = round3(self.saved_unit_cost * (self.quantity or Decimal("0")))
        else:
            self.saved_unit_cost = self.unit_cost()
            self.saved_total_cost = self.line_total_cost()

        super().save(*args, **kwargs)

    @cached_property
    def unit_cost_cached(self):
        return self.unit_cost()

    @cached_property
    def line_total_cost_cached(self):
        return self.line_total_cost()

    def unit_cost(self):
        period = self.stock_count.period if self.stock_count_id else None

        # ✅ Opening يدوي
        if self.stock_count_id and self.stock_count.type == "opening" and self.unit_cost_value is not None:
            return round3(self.unit_cost_value)

        if self.raw_material:
            raw = self.raw_material

            cost = raw.get_cost_from_purchases(period=period)
            if cost is None:
                cost = raw.get_cost_per_ingredient_unit(period=None)
            if cost is None:
                return None

            if self.unit_id:
                if raw.ingredient_unit_id == self.unit_id:
                    return round3(cost)

                if raw.storage_unit_id == self.unit_id:
                    if raw.storage_to_ingredient_factor:
                        return round3(cost * raw.storage_to_ingredient_factor)
                    if raw.purchase_price_per_storage_unit:
                        return round3(raw.purchase_price_per_storage_unit)

            return round3(cost)

        if self.semi_finished_product:
            product = self.semi_finished_product
            cost = product.compute_unit_cost(period=period)
            return round3(cost) if cost is not None else None

        return None

    def line_total_cost(self):
        cost = self.unit_cost()
        if cost is None or self.quantity is None:
            return None
        return round3(cost * self.quantity)

class InventoryIssueType(models.TextChoices):
    NON_SALES = "NON_SALES", "منصرف لأغراض غير المبيعات"
    ADJUSTMENT = "ADJUSTMENT", "تسوية/فاقد/هالك"
    OTHER = "OTHER", "أخرى"


class InventoryIssue(TimeStampedModel):
    """رأس حركات المنصرف لأغراض غير المبيعات (فاقد، عينة، إنتاج داخلي...)."""

    period = models.ForeignKey(
        Period,
        on_delete=models.PROTECT,
        verbose_name="الفترة",
    )
    issue_date = models.DateField("تاريخ الحركة")
    issue_type = models.CharField(
        "نوع الحركة",
        max_length=20,
        choices=InventoryIssueType.choices,
        default=InventoryIssueType.NON_SALES,
    )
    notes = models.TextField("ملاحظات", blank=True, null=True)

    class Meta:
        verbose_name = "حركة صرف من المستودع"
        verbose_name_plural = "حركات صرف المستودع"

    def __str__(self):
        return f"{self.get_issue_type_display()} - {self.issue_date} - {self.period}"


class InventoryIssueLine(TimeStampedModel):
    inventory_issue = models.ForeignKey(
        InventoryIssue,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="حركة الصرف",
    )

    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.PROTECT,
        verbose_name="مادة خام",
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        verbose_name="وحدة الصرف",
    )

    quantity = models.DecimalField(
        "الكمية المنصرفة",
        max_digits=16,
        decimal_places=4,
    )

    class Meta:
        verbose_name = "بند صرف مستودع"
        verbose_name_plural = "بنود صرف المستودع"

    def __str__(self):
        return f"{self.raw_material} - {self.quantity} {self.unit}"



from django.db import models

class BomTreeReport(models.Model):
    """
    نموذج وهمي فقط لعرض رابط التقرير داخل لوحة التحكم.
    لا جدول له في قاعدة البيانات.
    """
    class Meta:
        managed = False  # لا ينشئ جدول في قاعدة البيانات
        verbose_name = "تقرير شجرة المكونات (BOM Tree)"
        verbose_name_plural = "تقرير شجرة المكونات (BOM Tree)"
