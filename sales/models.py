# sales/models.py
from django.db import models
from decimal import Decimal, ROUND_HALF_UP

from costing.models import Product, Unit, RawMaterial
from expenses.models import Period


# -------------------- أدوات مساعدة عامة --------------------

def round3(value):
    """
    تقريب أي Decimal إلى ثلاث منازل عشرية.
    """
    if value is None:
        return None
    return Decimal(value).quantize(Decimal("0.000"), rounding=ROUND_HALF_UP)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("تاريخ آخر تعديل", auto_now=True)

    class Meta:
        abstract = True


# -------------------- ملخص المبيعات --------------------

class SalesSummary(models.Model):
    period = models.ForeignKey(
        Period,
        on_delete=models.PROTECT,
        related_name="sales_summaries",
        verbose_name="الفترة",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "ملخص مبيعات"
        verbose_name_plural = "ملخصات المبيعات"

    def __str__(self):
        return f"مبيعات - {self.period}"

    def total_amount(self):
        total = Decimal("0")
        for line in self.lines.all():
            if line.line_total is not None:
                total += line.line_total
        return total
    total_amount.short_description = "إجمالي قيمة المبيعات"

    def save(self, *args, **kwargs):
        """
        عند حفظ ملخص المبيعات:
        1) نحفظ السجل.
        2) نعيد توليد استهلاك المواد لهذه الفترة.
        """
        super().save(*args, **kwargs)
        from .models import generate_sales_consumption
        if self.period:
            generate_sales_consumption(self.period)


class SalesSummaryLine(models.Model):
    summary = models.ForeignKey(
        SalesSummary,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="الملخص",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        verbose_name="المنتج",
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        verbose_name="وحدة البيع",
    )
    quantity = models.DecimalField(
        "إجمالي الكمية المباعة",
        max_digits=18,
        decimal_places=4,
    )
    unit_price = models.DecimalField(
        "سعر البيع للوحدة",
        max_digits=18,
        decimal_places=4,
    )
    line_total = models.DecimalField(
        "إجمالي الصنف",
        max_digits=18,
        decimal_places=2,
        editable=False,
        default=0,
    )

    class Meta:
        verbose_name = "بند في ملخص المبيعات"
        verbose_name_plural = "بنود ملخص المبيعات"

    def __str__(self):
        return f"{self.product} ({self.summary})"

    def save(self, *args, **kwargs):
        qty = self.quantity or Decimal("0")
        price = self.unit_price or Decimal("0")
        self.line_total = qty * price
        super().save(*args, **kwargs)


# -------------------- تجميع استهلاك المواد --------------------

class SalesConsumptionSummary(models.Model):
    period = models.OneToOneField(
        Period,
        on_delete=models.CASCADE,
        verbose_name="الفترة"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تجميع استهلاك المواد"
        verbose_name_plural = "تجميعات استهلاك المواد"

    def __str__(self):
        return f"استهلاك - {self.period}"


class SalesConsumption(models.Model):
    """
    يسجل استهلاك مادة خام نتيجة مبيعات منتج نهائي معيّن في فترة معيّنة.

    الكميات هنا بوحدة الاستخدام الصغيرة (ingredient_unit) للمادة الخام.
    التحويل للوحدة الكبيرة (وحدة التخزين) يتم في التقارير عند الحاجة.
    """
    summary = models.ForeignKey(
        SalesConsumptionSummary,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="تجميع",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="المنتج النهائي",
    )

    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.CASCADE,
        verbose_name="المادة الخام",
        related_name="sales_consumptions",
        null=True,
        blank=True,
    )

    # الكمية المباعة من المنتج النهائي (للمعلومة / التتبع)
    quantity_sold = models.DecimalField(
        "الكمية المباعة من المنتج النهائي",
        max_digits=18,
        decimal_places=4,
    )

    # الاستهلاك الفعلي للمادة الخام بوحدة الاستخدام (small / ingredient_unit)
    quantity_consumed = models.DecimalField(
        "الكمية المستهلكة (وحدة الاستخدام)",
        max_digits=18,
        decimal_places=6,
    )

    # تكلفة وحدة الاستخدام من المادة الخام (أصغر وحدة)
    unit_cost = models.DecimalField(
        "تكلفة وحدة المادة (وحدة الاستخدام)",
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # إجمالي تكلفة المادة الخام المستهلكة
    total_cost = models.DecimalField(
        "إجمالي التكلفة",
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # تتبع المسار داخل شجرة الـ BOM
    source_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="المصدر",
        related_name="consumption_sources",
        null=True,
        blank=True,
    )
    source_type = models.CharField(
        "نوع المصدر",
        max_length=10,
        choices=[("final", "منتج نهائي"), ("semi", "منتج نصف مصنع")],
        null=True,
        blank=True,
    )
    level = models.PositiveIntegerField(
        "مستوى التفكيك",
        default=1,
    )

    class Meta:
        verbose_name = "استهلاك مادة خام"
        verbose_name_plural = "استهلاك المواد الخام"

    def __str__(self):
        component = self.raw_material or self.source_product
        return f"{self.product} ← {component} ({self.quantity_consumed})"

    # 🔹 كمية بوحدة التخزين (الكبيرة) – تستخدم في التقارير عند الحاجة
    def quantity_consumed_storage(self):
        """
        ترجع الكمية المكافئة بوحدة التخزين (storage_unit) للمادة الخام،
        بالاعتماد على دوال التحويل في RawMaterial.
        """
        if not self.raw_material:
            return None
        return self.raw_material.ingredient_to_storage(self.quantity_consumed)

    quantity_consumed_storage.short_description = "الكمية بوحدة التخزين"


# -------------------- دوال مساعدة / منطق التوليد --------------------

def get_quantity_sold(product, period):
    """
    ترجع إجمالي الكمية المباعة من منتج نهائي معيّن خلال فترة معيّنة،
    بالاعتماد على ملخص المبيعات SalesSummaryLine.
    """
    total_qty = (
        SalesSummaryLine.objects
        .filter(product=product, summary__period=period)
        .aggregate(total=models.Sum("quantity"))["total"] or Decimal("0")
    )
    return total_qty


from decimal import Decimal
from django.db import transaction

def generate_sales_consumption(period):
    """
    (مرحلة 1 - حل بسيط)
    - نفك BOM لكل منتج مصنع (نهائي + نصف مصنع)
    - نجمع الاستهلاك على مستوى (المنتج النهائي + المادة الخام) فقط
    - كل شيء يُحسب على أصغر وحدة (ingredient_unit) للمادة الخام
    """
    summary, _ = SalesConsumptionSummary.objects.get_or_create(period=period)

    # حذف القديم
    summary.lines.all().delete()

    # هنا نجمع الاستهلاك بدل إنشاء سطور أثناء التفكيك
    # key = (final_product_id, raw_material_id)
    acc = {}

    def add_raw(final_product, raw, sales_qty, qty_consumed):
        if qty_consumed is None:
            return
        qty_consumed = Decimal(qty_consumed)

        unit_cost = raw.get_cost_per_ingredient_unit(period=period)
        total_cost = (unit_cost * qty_consumed) if unit_cost is not None else None

        key = (final_product.id, raw.id)
        if key not in acc:
            acc[key] = {
                "final_product": final_product,
                "raw": raw,
                "sales_qty": Decimal(sales_qty or 0),
                "qty": Decimal("0"),
                "unit_cost": unit_cost,   # غالبًا ثابت للفترة
            }

        acc[key]["qty"] += qty_consumed
        # لو unit_cost موجود نعيد حساب الإجمالي في النهاية (أوضح وأضمن)
        # (خصوصًا لو كان None في بعض الحالات)

    def collect(final_product, current_product, sales_qty, required_qty, visited=None):
        """
        required_qty: الكمية المطلوبة من current_product لإنتاج المطلوب (بوحدة المنتج نفسه)
        """
        if visited is None:
            visited = set()

        if current_product.id in visited:
            return
        visited.add(current_product.id)

        bom = current_product.get_active_bom()
        if not bom:
            visited.remove(current_product.id)
            return

        bom_output_qty = bom.batch_output_quantity or Decimal("1")

        for item in bom.items.all():
            base_qty = item.quantity or Decimal("0")

            # كمية البند لكل 1 وحدة من current_product
            qty_per_unit = base_qty / bom_output_qty

            # الكمية الإجمالية المطلوبة من هذا البند
            qty_total = Decimal(required_qty) * qty_per_unit

            # 1) مادة خام مباشرة (حتى لو ليست "تصنيع" — طالما موجودة في BOM للمنتج النهائي)
            if item.raw_material:
                add_raw(final_product, item.raw_material, sales_qty, qty_total)

            # 2) منتج نصف مصنع -> نفك BOM له
            elif item.component_product and item.component_product.is_semi_finished:
                collect(
                    final_product=final_product,
                    current_product=item.component_product,
                    sales_qty=sales_qty,
                    required_qty=qty_total,
                    visited=visited
                )

        visited.remove(current_product.id)

    # تنفيذ
    with transaction.atomic():
        for final_product in Product.objects.filter(is_sellable=True):
            sales_qty = get_quantity_sold(final_product, period)
            if sales_qty and Decimal(sales_qty) > 0:
                collect(
                    final_product=final_product,
                    current_product=final_product,
                    sales_qty=sales_qty,
                    required_qty=sales_qty,
                    visited=set()
                )

        # إنشاء السطور النهائية (سطر واحد لكل مادة خام داخل كل منتج نهائي)
        rows = []
        for (_, _), v in acc.items():
            raw = v["raw"]
            qty = v["qty"]
            unit_cost = raw.get_cost_per_ingredient_unit(period=period)
            total_cost = (unit_cost * qty) if unit_cost is not None else None

            rows.append(SalesConsumption(
                summary=summary,
                product=v["final_product"],
                raw_material=raw,
                quantity_sold=v["sales_qty"],
                quantity_consumed=qty,     # أصغر وحدة
                unit_cost=unit_cost,
                total_cost=total_cost,
                # مرحلة أولى: بدون تتبع المصدر/المستوى لتجنب التكرارات
                source_product=None,
                source_type="final",
                level=1,
            ))

        SalesConsumption.objects.bulk_create(rows)
