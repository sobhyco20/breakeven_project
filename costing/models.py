from django.db import models
from decimal import Decimal


from decimal import Decimal, ROUND_HALF_UP

def round3(value):
    if value is None:
        return None
    return value.quantize(Decimal("0.000"), rounding=ROUND_HALF_UP)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ آخر تعديل")

    class Meta:
        abstract = True


class Unit(TimeStampedModel):
    name = models.CharField("اسم الوحدة", max_length=100)
    abbreviation = models.CharField("الاختصار", max_length=20, blank=True)

    def __str__(self):
        return self.abbreviation or self.name

    class Meta:
        verbose_name = "وحدة قياس"
        verbose_name_plural = "وحدات القياس"


class RawMaterial(TimeStampedModel):
    sku = models.CharField("كود المادة / SKU", max_length=50, unique=True, null=True, blank=True)
    name = models.CharField("اسم المادة الخام", max_length=200)

    storage_unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT,
        related_name="raw_materials_storage",
        verbose_name="وحدة التخزين",
        null=True, blank=True
    )

    ingredient_unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT,
        related_name="raw_materials_ingredient",
        verbose_name="وحدة الاستخدام",
        null=True, blank=True
    )

    storage_to_ingredient_factor = models.DecimalField(
        "عدد وحدات الاستخدام في وحدة التخزين",
        max_digits=12, decimal_places=4,
        null=True, blank=True
    )

    purchase_price_per_storage_unit = models.DecimalField(
        "سعر وحدة التخزين", max_digits=12, decimal_places=4,
        null=True, blank=True
    )

    cost_per_ingredient_unit = models.DecimalField(
        "تكلفة وحدة الاستخدام",
        max_digits=12, decimal_places=6,
        null=True, blank=True,
        editable=False
    )

    # --------------------------------------------------------
    # تحديث تلقائي لتكلفة أصغر وحدة بناءً على التكلفة المخزنة
    # --------------------------------------------------------
    def update_cost_per_ingredient_unit(self):
        if self.storage_to_ingredient_factor and self.purchase_price_per_storage_unit:
            value = self.purchase_price_per_storage_unit / self.storage_to_ingredient_factor
            self.cost_per_ingredient_unit = round3(value)
        else:
            self.cost_per_ingredient_unit = None


    # --------------------------------------------------------
    # حساب التكلفة من ملخصات المشتريات (الوحدة الكبيرة)
    # --------------------------------------------------------
    def get_cost_from_purchases(self, period=None):
        """
        إرجاع *أحدث تكلفة* لأصغر وحدة (ingredient_unit) محسوبة من ملخصات المشتريات.

        المنطق:
        - نختار آخر سطر مشتريات لهذه المادة الخام (بناءً على تاريخ الفترة).
        - نأخذ منه unit_cost (سعر وحدة التخزين).
        - نحوله إلى تكلفة وحدة الاستخدام إذا كان هناك storage_to_ingredient_factor.
        """

        from purchases.models import PurchaseSummaryLine

        qs = PurchaseSummaryLine.objects.filter(raw_material=self)

        # لو فترة محددة: نأخذ كل المشتريات حتى هذه الفترة
        if period is not None and getattr(period, "start_date", None):
            qs = qs.filter(summary__period__start_date__lte=period.start_date)

        latest_line = qs.order_by("-summary__period__start_date", "-id").first()
        if not latest_line or latest_line.unit_cost is None:
            return None

        cost_per_storage_unit = latest_line.unit_cost  # تكلفة وحدة التخزين (مثلاً كرتونة / جالون)

        # لو ما فيش معامل تحويل نرجع تكلفة وحدة التخزين كما هي
        if not self.storage_to_ingredient_factor or self.storage_to_ingredient_factor == 0:
            return round3(cost_per_storage_unit)

        # تكلفة أصغر وحدة = تكلفة وحدة التخزين ÷ عدد الوحدات الصغيرة داخل وحدة التخزين
        cost_per_ingredient_unit = cost_per_storage_unit / self.storage_to_ingredient_factor
        return round3(cost_per_ingredient_unit)

    # --------------------------------------------------------
    # المصدر النهائي لتكلفة الوحدة الصغيرة
    # --------------------------------------------------------
    def get_cost_per_ingredient_unit(self, period=None):
        # 1) نحاول أولاً من أحدث مشتريات
        cost = self.get_cost_from_purchases(period=period)
        if cost is not None:
            return cost

        # 2) لو ما فيش مشتريات، نستخدم القيمة المخزنة (قد تكون من فترة سابقة)
        if self.cost_per_ingredient_unit is not None:
            return round3(self.cost_per_ingredient_unit)

        # 3) في آخر خيار، نحسبها من سعر وحدة التخزين ومعامل التحويل
        if self.storage_to_ingredient_factor and self.purchase_price_per_storage_unit:
            value = self.purchase_price_per_storage_unit / self.storage_to_ingredient_factor
            return round3(value)

        return None

    def convert_qty_to_storage(self, quantity, unit=None):
        """
        ترجع الكمية بوحدة التخزين (storage_unit).

        - لو الكمية أصلاً بوحدة التخزين → ترجع كما هي.
        - لو بوحدة الاستخدام → تقسم على معامل التحويل.
        - لو وحدة غير معروفة → ترجع الكمية كما هي.
        """
        if quantity is None:
            return Decimal("0")

        qty = Decimal(str(quantity))

        # نحول الـ unit إلى id لو جاء كـ object
        unit_id = None
        if unit is None:
            unit_id = None
        elif hasattr(unit, "id"):
            unit_id = unit.id
        else:
            unit_id = unit

        # إن كانت نفس وحدة التخزين -> نرجعها كما هي
        if self.storage_unit_id and unit_id == self.storage_unit_id:
            return round3(qty)

        # إن كانت وحدة الاستخدام -> نقسم على معامل التحويل
        if self.ingredient_unit_id and unit_id == self.ingredient_unit_id:
            factor = self.storage_to_ingredient_factor or Decimal("1")
            if factor == 0:
                return round3(qty)
            return round3(qty / factor)

        # لو الوحدة مش معروفة نفترض أنها بالفعل بوحدة التخزين
        return round3(qty)

    # دالة مساعدة خاصة بحالتنا: كمية بوحدة الاستخدام وتحويلها للوحدة الكبيرة
    def ingredient_to_storage(self, quantity):
        return self.convert_qty_to_storage(quantity, unit=self.ingredient_unit_id)

    # --------------------------------------------------------
    # تحديث تلقائي قبل الحفظ
    # --------------------------------------------------------
    def save(self, *args, **kwargs):
        self.update_cost_per_ingredient_unit()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} - {self.name}" if self.sku else self.name

    class Meta:
        verbose_name = "مادة خام"
        verbose_name_plural = "المواد الخام"




class Product(TimeStampedModel):
    code = models.CharField("كود المنتج", max_length=50, unique=True)

    # 🆕 حقلين للأسماء
    name = models.CharField("اسم المنتج بالعربي", max_length=200)
    name_en = models.CharField("اسم المنتج بالإنجليزية", max_length=200, blank=True, null=True)

    base_unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT,
        verbose_name="وحدة المنتج (بيع/إنتاج)",
        help_text="مثل: طبق، حبة، كيلو"
    )

    is_sellable = models.BooleanField("يُباع للعميل", default=True)
    is_semi_finished = models.BooleanField(
        "منتج نصف مصنع", default=False,
        help_text="يُستخدم كمكوّن في منتج آخر"
    )

    selling_price_per_unit = models.DecimalField(
        "سعر بيع الوحدة",
        max_digits=12, decimal_places=4, null=True, blank=True
    )

    def __str__(self):
        # نعرض الاسم العربي في القوائم
        return f"{self.code} - {self.name}"

    def get_active_bom(self):
        return self.boms.filter(is_active=True).first()

    def compute_unit_cost(self, period=None, visited=None):
        from decimal import Decimal

        if visited is None:
            visited = set()

        # حماية من الدوران في حالة وصفات تعتمد على بعضها
        if self.id in visited:
            return None
        visited.add(self.id)

        bom = self.get_active_bom()
        if not bom:
            return None

        # 1) إجمالي تكلفة الوصفة
        total_cost = bom.total_recipe_cost(period=period)

        # 2) كمية الإنتاج الإجمالية
        qty = bom.batch_output_quantity or Decimal("0")
        if qty == 0:
            return None

        # 3) تكلفة الوحدة = الإجمالي ÷ الكمية
        unit_cost = total_cost / qty
        return round3(unit_cost)

    
    
    class Meta:
        verbose_name = "منتج"
        verbose_name_plural = "المنتجات"


class BillOfMaterial(TimeStampedModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="boms",
        verbose_name="المنتج"
    )
    name = models.CharField("اسم الوصفة", max_length=200, blank=True)
    is_active = models.BooleanField("فعّالة", default=True)

    batch_output_quantity = models.DecimalField(
        "كمية الإنتاج الإجمالية",
        max_digits=12, decimal_places=4,
        null=True, blank=True,
        help_text="مثال: 8000 جرام أو 30 طبق"
    )
    batch_output_unit = models.ForeignKey(
        Unit, on_delete=models.PROTECT,
        verbose_name="وحدة كمية الإنتاج",
        null=True, blank=True,
    )

    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="تكلفة الوحدة الواحدة"
    )

    # 🔹 الحقل الجديد لتخزين تكلفة الوحدة لاستخدامها في التقارير
    unit_cost_final = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="تكلفة الوحدة (محفوظة)"
    )


    def save(self, *args, **kwargs):
        """
        عند إنشاء BOM لأول مرة لا يكون له pk ولا بنود،
        لذلك لا نحاول حساب التكاليف إلا لو له pk فعليًا.
        """
        from decimal import Decimal

        # في حالة التعديل على سجل موجود
        if self.pk and self.batch_output_quantity and self.batch_output_quantity > 0:
            total = self.total_recipe_cost()
            if total is not None:
                self.unit_cost = round3(total / self.batch_output_quantity)
                self.unit_cost_final = self.unit_cost
            else:
                self.unit_cost = None
                self.unit_cost_final = None
        else:
            # في حالة الإضافة الأولى أو عدم وجود كمية إنتاج
            self.unit_cost = None
            self.unit_cost_final = None

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or f"الوصفة للمنتج {self.product}"

    def total_recipe_cost(self, period=None):
        """
        مجموع تكلفة كل بنود الوصفة.
        لو الـ BOM جديد (بدون pk) نرجع 0 بدل ما نلمس self.items.
        """
        from decimal import Decimal

        if not self.pk:
            return Decimal("0")

        total = Decimal("0")
        for item in self.items.all():
            line = item.line_total_cost(period=period)
            if line:
                total += line
        return round3(total)

    class Meta:
        verbose_name = "وصفة (BOM)"
        verbose_name_plural = "الوصفات (BOMs)"




class BOMItem(TimeStampedModel):
    bom = models.ForeignKey(
        BillOfMaterial, on_delete=models.CASCADE, related_name="items",
        verbose_name="الوصفة"
    )

    raw_material = models.ForeignKey(
        RawMaterial, on_delete=models.PROTECT,
        null=True, blank=True, related_name="bom_items",
        verbose_name="مادة خام"
    )
    component_product = models.ForeignKey(
        Product, on_delete=models.PROTECT,
        null=True, blank=True, related_name="component_in_boms",
        verbose_name="منتج مكوّن (نصف مصنع)",
        help_text="لو المكوّن منتج نصف مصنع أو منتج مطبوخ بكود"
    )

    quantity = models.DecimalField(
        "الكمية المطلوبة لإنتاج 1 وحدة من المنتج",
        max_digits=12, decimal_places=4,
    )

    # unit / unit_cost / line_total_cost كما هي عندك

    def __str__(self):
        item_name = self.raw_material or self.component_product
        return f"{self.bom} -> {item_name} ({self.quantity})"

    # المادة المستخدمة (مادة خام أو منتج)
    def material(self):
        return self.raw_material or self.component_product

    # وحدة الكمية
    def unit(self):
        if self.raw_material and self.raw_material.ingredient_unit:
            return self.raw_material.ingredient_unit
        if self.component_product and self.component_product.base_unit:
            return self.component_product.base_unit
        return None

    def unit_cost(self, period=None):
        if self.raw_material:
            cost = self.raw_material.get_cost_per_ingredient_unit(period=period)
        elif self.component_product:
            cost = self.component_product.compute_unit_cost(period=period)
        else:
            cost = None

        return round3(cost) if cost is not None else None



    def line_total_cost(self, period=None):
        from decimal import Decimal
        unit_cost = self.unit_cost(period=period)
        if unit_cost is None:
            return None

        total = unit_cost * (self.quantity or Decimal("0"))
        # إجمالي الصنف مقرب لـ 3 أرقام عشرية
        return round3(total)


    class Meta:
        verbose_name = "عنصر في الوصفة"
        verbose_name_plural = "عناصر الوصفة"
