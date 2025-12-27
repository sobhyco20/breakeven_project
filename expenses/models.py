# expenses/models.py
from decimal import Decimal
from django.db import models


from django.core.exceptions import ValidationError
# =========================
# Base
# =========================
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("تاريخ آخر تعديل", auto_now=True)

    class Meta:
        abstract = True


# =========================
# Period
# =========================
class Period(TimeStampedModel):
    YEAR_CHOICES = [(y, str(y)) for y in range(2024, 2031)]
    
    year = models.IntegerField("السنة", choices=YEAR_CHOICES, default=2025)
    month = models.IntegerField("الشهر (1-12)", default=1)

    name = models.CharField("اسم الفترة", max_length=100, blank=True)
    start_date = models.DateField("من تاريخ")
    end_date = models.DateField("إلى تاريخ")
    is_closed = models.BooleanField("مقفلة؟", default=False)

    inv_opening_enabled = models.BooleanField("السماح بفتح جرد أول الفترة", default=False)
    inv_opening_enabled_at = models.DateTimeField("تاريخ فتح جرد أول الفترة", null=True, blank=True)

    # اختياري (مفيد جداً): منع إعادة الفتح بعد الاعتماد
    inv_opening_once_only = models.BooleanField("جرد أول الفترة مرة واحدة فقط", default=True)

    # اختياري: رسالة إدارية
    inv_opening_note = models.CharField("ملاحظة فتح الجرد", max_length=200, blank=True, null=True)

    allow_opening_stock = models.BooleanField(
        "السماح بفتح جرد أول المدة",
        default=False,
        help_text="لا يُفتح جرد أول المدة إلا إذا تم تفعيل هذا الخيار من الفترات."
    )

    class Meta:
        verbose_name = "فترة"
        verbose_name_plural = "فترات"
        unique_together = ("year", "month")
        ordering = ["year", "month"]


        

    def __str__(self):
        return self.name or f"{self.year}-{self.month:02d}"


# =========================
# NEW (Target Structure) ✅
# =========================
class ExpenseCategory(models.Model):
    class Nature(models.TextChoices):
        OP = "OP", "تشغيلي"
        SA = "SA", "بيعي"
        AD = "AD", "إداري"

    class Directness(models.TextChoices):
        DIRECT = "DIRECT", "مباشر"
        INDIRECT = "INDIRECT", "غير مباشر"

    class Frequency(models.TextChoices):
        MONTHLY = "MONTHLY", "شهري"
        YEARLY = "YEARLY", "سنوي"
        ADHOC = "ADHOC", "غير دوري"

    class Behavior(models.TextChoices):
        FIXED = "FIXED", "ثابت"
        VARIABLE = "VARIABLE", "متغير"

    code = models.CharField("الكود", max_length=30, unique=True)
    name = models.CharField("اسم التصنيف", max_length=200)

    nature = models.CharField("طبيعة المصروف", max_length=2, choices=Nature.choices)
    directness = models.CharField("مباشر/غير مباشر", max_length=10, choices=Directness.choices)
    frequency = models.CharField("دورية الصرف", max_length=10, choices=Frequency.choices, default=Frequency.MONTHLY)
    behavior = models.CharField("ثابت/متغير", max_length=10, choices=Behavior.choices, default=Behavior.FIXED)

    is_active = models.BooleanField("نشط", default=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "تصنيف مصروف"
        verbose_name_plural = "تصنيفات المصروفات"

    def __str__(self):
        return f"{self.code} - {self.name}"


class ExpenseItem(models.Model):
    code = models.CharField("كود المصروف", max_length=30, unique=True)
    name = models.CharField("اسم المصروف", max_length=200)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, verbose_name="تصنيف المصروف")

    default_amount = models.DecimalField("مبلغ افتراضي", max_digits=18, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField("نشط", default=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "اسم مصروف"
        verbose_name_plural = "أسماء المصروفات"

    def __str__(self):
        return f"{self.code} - {self.name}"


# =========================
# OLD (Keep Temporarily) ✅
# لتفادي كسر البيانات القديمة أثناء الترحيل
# =========================
class ExpenseBehavior(models.TextChoices):
    FIXED = "FIXED", "ثابتة"
    VARIABLE = "VARIABLE", "متغيرة"
    MIXED = "MIXED", "مختلطة"


class ExpenseType(TimeStampedModel):
    name = models.CharField("اسم المصروف", max_length=200)
    category = models.CharField(
        "تصنيف المصروف",
        max_length=10,
        choices=ExpenseBehavior.choices,
        default=ExpenseBehavior.FIXED,
    )
    is_accrual = models.BooleanField(
        "مصروف مستحق",
        default=False,
        help_text="هل المصروف مستحق (غير مدفوع)؟",
    )

    class Meta:
        verbose_name = "نوع مصروف (قديم)"
        verbose_name_plural = "أنواع المصروفات (قديمة)"

    def __str__(self):
        return self.name


class ExpenseEntry(TimeStampedModel):
    # ✅ ما زال مرتبطًا بالقديم مؤقتًا، سنحوّله لاحقًا إلى ExpenseItem
    expense_type = models.ForeignKey(
        ExpenseType,
        on_delete=models.PROTECT,
        related_name="entries",
        verbose_name="نوع المصروف",
    )
    period = models.ForeignKey(
        Period,
        on_delete=models.PROTECT,
        related_name="expense_entries",
        verbose_name="الفترة",
    )
    amount = models.DecimalField("المبلغ", max_digits=14, decimal_places=4)
    notes = models.TextField("ملاحظات", blank=True)

    class Meta:
        verbose_name = "قيد مصروف"
        verbose_name_plural = "قيود المصروفات"

    def __str__(self):
        return f"{self.expense_type} - {self.period} - {self.amount}"

# ===== Monthly Entry (NEW) =====

class ExpenseBatch(TimeStampedModel):
    """
    كشف المصروفات الشهريةة: سجل واحد لكل فترة
    """
    period = models.OneToOneField(Period, on_delete=models.PROTECT, verbose_name="الفترة")
    notes = models.CharField("ملاحظات", max_length=250, blank=True)

    class Meta:
        verbose_name = "مصروفات الفترة"
        verbose_name_plural = "مصروفات الفترات"

    def __str__(self):
        return f"مصروفات فترة {self.period}"

    def clean(self):
        super().clean()
        if self.period and self.period.is_closed:
            raise ValidationError("هذه الفترة مقفلة، لا يمكن تعديل/حفظ المصروفات عليها.")

    def save(self, *args, **kwargs):
        self.full_clean()  # ✅ يمنع الحفظ لو الفترة مقفلة
        return super().save(*args, **kwargs)

class ExpenseLine(models.Model):
    """
    سطر لكل مصروف (ExpenseItem) داخل المسير
    """
    batch = models.ForeignKey(ExpenseBatch, on_delete=models.CASCADE, related_name="lines", verbose_name="المسير")
    item = models.ForeignKey(ExpenseItem, on_delete=models.PROTECT, verbose_name="اسم المصروف")
    amount = models.DecimalField("المبلغ", max_digits=18, decimal_places=2, default=Decimal("0.00"))
    notes = models.CharField("ملاحظات", max_length=250, blank=True)

    class Meta:
        unique_together = ("batch", "item")
        ordering = ("item__code",)
        verbose_name = "سطر مصروف"
        verbose_name_plural = "سطور المصروفات"

    def __str__(self):
        return f"{self.batch} | {self.item} | {self.amount}"

    def clean(self):
        super().clean()
        if self.batch_id and self.batch.period and self.batch.period.is_closed:
            raise ValidationError("هذه الفترة مقفلة، لا يمكن تعديل/حفظ سطور المصروفات.")

    def save(self, *args, **kwargs):
        self.full_clean()  # ✅ يمنع الحفظ لو الفترة مقفلة
        return super().save(*args, **kwargs)