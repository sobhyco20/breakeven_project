from .models import Unit, RawMaterial, Product, BillOfMaterial, BOMItem
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from .forms import RawMaterialImportForm, ProductImportForm
import pandas as pd
from django.db.models import Q
from django.http import HttpResponse
from decimal import Decimal
from .forms import BOMImportForm

from django.urls import reverse
from django.utils.html import format_html

from .models import Unit, RawMaterial, Product, BillOfMaterial, BOMItem
from django.contrib import admin, messages
from django.urls import path, reverse   # ✅ أضفنا reverse
from django.shortcuts import render, redirect
from django.utils.html import format_html  # ✅ أضفنا format_html


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "abbreviation")
    search_fields = ("name", "abbreviation")


@admin.register(RawMaterial)
class RawMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "storage_unit",
        "ingredient_unit",
        "storage_to_ingredient_factor",
        "purchase_price_per_storage_unit",
        "cost_per_ingredient_unit",
    )
    search_fields = ("sku", "name")
    list_filter = ("storage_unit", "ingredient_unit")
    readonly_fields = ("cost_per_ingredient_unit",)

    change_list_template = "admin/costing/rawmaterial_changelist.html"  # 👈 لاستخدام زر مخصص

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="costing_rawmaterial_import_excel",
            ),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        """استيراد المواد الخام من ملف إكسل مطابق للهيكل raw.xlsx."""
        if request.method == "POST":
            form = RawMaterialImportForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = form.cleaned_data["excel_file"]
                try:
                    df = pd.read_excel(excel_file)

                    cols = {c.strip(): c for c in df.columns}

                    name_col = cols.get("name") or cols.get("الاسم")  # احتياط
                    sku_col = cols.get("sku") or cols.get("كود")      # احتياط
                    storage_unit_col = cols.get("storage_unit")
                    ingredient_unit_col = cols.get("ingredient_unit")
                    factor_col = cols.get("storage_to_ingredient_factor")
                    price_col = cols.get("purchase_price")  # لو حبيت تضيفه في الإكسل لاحقاً

                    if not (name_col and sku_col and storage_unit_col and ingredient_unit_col and factor_col):
                        messages.error(
                            request,
                            "تأكد أن ملف الإكسل يحتوي الأعمدة: name, sku, storage_unit, ingredient_unit, storage_to_ingredient_factor",
                        )
                        return redirect("admin:costing_rawmaterial_changelist")

                    for _, row in df.iterrows():
                        sku = str(row[sku_col]).strip()
                        name = str(row[name_col]).strip()

                        storage_unit_name = str(row[storage_unit_col]).strip()
                        ingredient_unit_name = str(row[ingredient_unit_col]).strip()
                        factor = row[factor_col]

                        storage_unit, _ = Unit.objects.get_or_create(name=storage_unit_name)
                        ingredient_unit, _ = Unit.objects.get_or_create(name=ingredient_unit_name)

                        purchase_price = None
                        if price_col and not pd.isna(row[price_col]):
                            purchase_price = row[price_col]

                        RawMaterial.objects.update_or_create(
                            sku=sku,
                            defaults={
                                "name": name,
                                "storage_unit": storage_unit,
                                "ingredient_unit": ingredient_unit,
                                "storage_to_ingredient_factor": factor,
                                "purchase_price_per_storage_unit": purchase_price,
                            },
                        )

                    messages.success(request, "تم استيراد المواد الخام من ملف الإكسل بنجاح.")
                    return redirect("admin:costing_rawmaterial_changelist")

                except Exception as e:
                    messages.error(request, f"حدث خطأ أثناء قراءة الملف: {e}")
        else:
            form = RawMaterialImportForm()

        context = {
            "form": form,
            "title": "استيراد المواد الخام من إكسل",
        }
        return render(request, "admin/costing/rawmaterial_import.html", context)


class RawBOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 1

    autocomplete_fields = ("raw_material", "component_product")
    class Media:
        js = ("admin/js/bomitem.js",)

    fields = (
        "raw_material",
        "component_product",
        "quantity",
        "unit_cost_display",
        "line_total_cost_display",
    )

    readonly_fields = ("unit_cost_display", "line_total_cost_display")

    def unit_cost_display(self, obj):
        return obj.unit_cost()
    unit_cost_display.short_description = "تكلفة الوحدة"

    def line_total_cost_display(self, obj):
        return obj.line_total_cost()
    line_total_cost_display.short_description = "إجمالي تكلفة الصنف"


class ProductBOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 1
    autocomplete_fields = ("component_product",)

    fields = (
        "component_product",
        "quantity",
        "display_unit",
        "display_unit_cost",
        "display_line_total_cost",
    )
    readonly_fields = ("display_unit", "display_unit_cost", "display_line_total_cost")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(component_product__isnull=False)

    def display_unit(self, obj):
        return obj.unit()
    display_unit.short_description = "وحدة الكمية"

    def display_unit_cost(self, obj):
        return obj.unit_cost()
    display_unit_cost.short_description = "تكلفة الوحدة"

    def display_line_total_cost(self, obj):
        return obj.line_total_cost()
    display_line_total_cost.short_description = "إجمالي تكلفة الصنف"


@admin.register(BillOfMaterial)
class BillOfMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "name",
        "is_active",
        "display_total_recipe_cost",
        "unit_cost_final",   # ✅ عرض تكلفة الوحدة المحفوظة في قائمة الوصفات
    )
    list_filter = ("is_active",)
    inlines = [RawBOMItemInline, ProductBOMItemInline]
    change_list_template = "admin/costing/billofmaterial_changelist.html"

    search_fields = (
        'name',
        'product__name',
        'product__id',
    )

    # ✅ نجعل الحقول المحسوبة للقراءة فقط
    readonly_fields = (
        "display_total_recipe_cost",
        "unit_cost",        # تكلفة الوحدة المحسوبة
        "unit_cost_final",  # تكلفة الوحدة المحفوظة
    )

    # ✅ ترتيب الحقول في نموذج الإضافة/التعديل
    fields = (
        "product",
        "name",
        "is_active",
        "batch_output_quantity",
        "batch_output_unit",
        "display_total_recipe_cost",
        "unit_cost",
        "unit_cost_final",
    )

    def display_total_recipe_cost(self, obj):
        if not obj or not obj.pk:
            return "—"
        return obj.total_recipe_cost()

    display_total_recipe_cost.short_description = "إجمالي تكلفة الوصفة"


    # -------------------- URLs مخصصة --------------------
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "download-template/",
                self.admin_site.admin_view(self.download_template),
                name="costing_billofmaterial_download_template",
            ),
            path(
                "import-bom-excel/",
                self.admin_site.admin_view(self.import_bom_excel),
                name="costing_billofmaterial_import_bom_excel",
            ),
        ]
        return custom_urls + urls

    # -------------------- 1) تحميل قالب BOM فارغ --------------------
    def download_template(self, request):
        """
        تحميل قالب إكسل فارغ لرؤوس أعمدة الوصفة (BOM)
        بدون أي بيانات منتجات.
        """
        columns = [
            "كود المنتج النهائي",
            "اسم المنتج النهائي (اختياري)",
            "اسم الوصفة (اختياري)",
            "كمية الإنتاج الإجمالية (اختياري)",
            "وحدة كمية الإنتاج (اختياري)",
            "كود المادة الخام (اختياري)",
            "اسم المادة الخام (اختياري)",
            "كود المنتج المكوّن (اختياري)",
            "الكمية المطلوبة لإنتاج 1 وحدة من المنتج",
        ]

        df = pd.DataFrame(columns=columns)

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="bom_template.xlsx"'

        with pd.ExcelWriter(response, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="BOM", index=False)

        return response

    # -------------------- 2) استيراد BOM من الإكسل --------------------
    # -------------------- 2) استيراد BOM من الإكسل --------------------
    def import_bom_excel(self, request):
        if request.method == "POST":
            form = BOMImportForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = form.cleaned_data["excel_file"]

                try:
                    df = pd.read_excel(excel_file)
                    cols = {c.strip(): c for c in df.columns}

                    # أعمدة القالب
                    product_code_col = cols.get("كود المنتج النهائي")
                    product_name_col = cols.get("اسم المنتج النهائي (اختياري)")
                    bom_name_col = cols.get("اسم الوصفة (اختياري)")
                    batch_qty_col = cols.get("كمية الإنتاج الإجمالية (اختياري)")
                    batch_unit_col = cols.get("وحدة كمية الإنتاج (اختياري)")

                    raw_sku_col = cols.get("كود المادة الخام (اختياري)")
                    raw_name_col = cols.get("اسم المادة الخام (اختياري)")
                    component_code_col = cols.get("كود المنتج المكوّن (اختياري)")
                    qty_col = cols.get("الكمية المطلوبة لإنتاج 1 وحدة من المنتج")

                    if not (product_code_col and qty_col and (raw_sku_col or component_code_col)):
                        messages.error(
                            request,
                            "تأكد أن ملف الإكسل يحتوي الأعمدة: "
                            "كود المنتج النهائي، الكمية المطلوبة، "
                            "وأحد الأعمدة: كود المادة الخام (اختياري) أو كود المنتج المكوّن (اختياري)."
                        )
                        return redirect("admin:costing_billofmaterial_changelist")

                    from decimal import Decimal

                    # وحدة افتراضية في حال احتجنا لإنشاء منتج جديد
                    default_unit, _ = Unit.objects.get_or_create(
                        name="وحدة", defaults={"abbreviation": "وحدة"}
                    )

                    bom_cache = {}
                    cleared_boms = set()

                    current_product = None
                    current_bom = None
                    current_bom_key = None

                    for _, row in df.iterrows():
                        # لو الصف كله فاضي
                        if all(pd.isna(v) for v in row):
                            continue

                        # ---------------- 1) تحديد / إنشاء المنتج النهائي ----------------
                        new_product = None

                        raw_val = row[product_code_col] if product_code_col in row.index else None
                        has_code_in_file = raw_val is not None and not pd.isna(raw_val) and str(raw_val).strip() != ""

                        if has_code_in_file:
                            code_str = str(raw_val).strip()
                            if code_str:
                                # نحاول نجيب المنتج
                                new_product = Product.objects.filter(code=code_str).first()

                            # لو مش موجود → ننشئ منتج جديد
                            if not new_product:
                                name_str = ""
                                if product_name_col and not pd.isna(row[product_name_col]):
                                    name_str = str(row[product_name_col]).strip()
                                if not name_str:
                                    name_str = code_str  # الاسم = الكود لو مفيش اسم

                                new_product = Product.objects.create(
                                    code=code_str,
                                    name=name_str,
                                    name_en="",
                                    base_unit=default_unit,
                                    selling_price_per_unit=Decimal("0"),
                                    is_sellable=True,
                                    is_semi_finished=False,
                                )

                            # في جميع الأحوال طالما فيه كود في الصف → نحدّث current_product
                            current_product = new_product

                        else:
                            # مفيش كود في الصف:
                            # نستخدم current_product لو موجود، أو نحاول بالاسم لأول مرة فقط
                            if current_product is None and product_name_col and not pd.isna(row[product_name_col]):
                                pname = str(row[product_name_col]).strip()
                                if pname:
                                    current_product = Product.objects.filter(name=pname).first()

                        # لو ما زال مفيش منتج → نتجاهل الصف
                        if not current_product:
                            continue

                        product = current_product

                        # ---------------- 2) تحديد / إنشاء الـ BOM ----------------
                        if bom_name_col and not pd.isna(row[bom_name_col]):
                            bom_name = str(row[bom_name_col]).strip()
                        else:
                            bom_name = f"الوصفة الافتراضية لـ {product.name}"

                        bom_key = (product.id, bom_name)

                        if (current_bom is None) or (bom_key != current_bom_key):
                            if bom_key in bom_cache:
                                bom = bom_cache[bom_key]
                            else:
                                bom, _ = BillOfMaterial.objects.get_or_create(
                                    product=product,
                                    name=bom_name,
                                    defaults={"is_active": True},
                                )
                                bom_cache[bom_key] = bom

                            current_bom = bom
                            current_bom_key = bom_key

                            # نحدّث رأس الوصفة + نحذف البنود القديمة مرة واحدة لكل BOM
                            if bom_key not in cleared_boms:
                                updated_header = False

                                if batch_qty_col and not pd.isna(row[batch_qty_col]):
                                    try:
                                        bom.batch_output_quantity = Decimal(str(row[batch_qty_col]))
                                        updated_header = True
                                    except Exception:
                                        pass

                                if batch_unit_col and not pd.isna(row[batch_unit_col]):
                                    unit_name = str(row[batch_unit_col]).strip()
                                    if unit_name:
                                        unit, _ = Unit.objects.get_or_create(
                                            name=unit_name,
                                            defaults={"abbreviation": unit_name},
                                        )
                                        bom.batch_output_unit = unit
                                        updated_header = True

                                if updated_header:
                                    bom.save()

                                bom.items.all().delete()
                                cleared_boms.add(bom_key)

                        bom = current_bom

                        # ---------------- 3) تحديد المكوّن ----------------
                        raw = None
                        component_product = None

                        if raw_sku_col and not pd.isna(row[raw_sku_col]):
                            sku = str(row[raw_sku_col]).strip()
                            if sku:
                                raw = RawMaterial.objects.filter(sku=sku).first()

                        if not raw and raw_name_col and not pd.isna(row[raw_name_col]):
                            rname = str(row[raw_name_col]).strip()
                            if rname:
                                raw = RawMaterial.objects.filter(name=rname).first()

                        if not raw and component_code_col and not pd.isna(row[component_code_col]):
                            comp_code = str(row[component_code_col]).strip()
                            if comp_code:
                                component_product = Product.objects.filter(code=comp_code).first()

                        if not raw and not component_product:
                            continue

                        # ---------------- 4) الكمية المطلوبة ----------------
                        qval = row[qty_col]
                        if pd.isna(qval):
                            continue

                        try:
                            quantity = Decimal(str(qval))
                        except Exception:
                            continue

                        if quantity <= 0:
                            continue

                        # ---------------- 5) إنشاء بند الوصفة ----------------
                        BOMItem.objects.create(
                            bom=bom,
                            raw_material=raw,
                            component_product=component_product,
                            quantity=quantity,
                        )

                    messages.success(request, "✅ تم استيراد الوصفات (BOM) من ملف الإكسل، مع إنشاء المنتجات الجديدة تلقائيًا.")
                    return redirect("admin:costing_billofmaterial_changelist")

                except Exception as e:
                    messages.error(request, f"حدث خطأ أثناء قراءة الملف: {e}")
                    return redirect("admin:costing_billofmaterial_changelist")
        else:
            form = BOMImportForm()

        context = {
            "form": form,
            "title": "استيراد الوصفات (BOM) من إكسل",
        }
        return render(request, "admin/costing/billofmaterial_import.html", context)



@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "name_en",
        "base_unit",
        "is_sellable",
        "is_semi_finished",
        "selling_price_per_unit",
        "open_bom_report",          # ✅ عمود جديد
    )
    list_filter = ("is_sellable", "is_semi_finished", "base_unit")
    search_fields = ("code", "name", "name_en")

    change_list_template = "admin/costing/product_changelist.html"

    # زر فتح تقرير شجرة المكونات
    def open_bom_report(self, obj):
        url = reverse("inventory:bom_tree_report") + f"?product={obj.id}&qty=1"
        return format_html('<a href="{}" target="_blank">عرض شجرة المكوّنات</a>', url)

    open_bom_report.short_description = "تقرير المكونات"
    open_bom_report.allow_tags = True



    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="costing_product_import_excel",
            ),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        """استيراد المنتجات من ملف إكسل (أعمدة عربية حسب الملف المرسل)."""
        if request.method == "POST":
            form = ProductImportForm(request.POST, request.FILES)
            if form.is_valid():
                excel_file = form.cleaned_data["excel_file"]
                try:
                    df = pd.read_excel(excel_file)

                    cols = {c.strip(): c for c in df.columns}

                    name_ar_col = cols.get("الااسم بالعربي") or cols.get("الاسم بالعربي")
                    name_en_col = cols.get("الاسم بالانجليزية")
                    code_col = cols.get("كود تعريف المنتج")
                    price_col = cols.get("سعر البيع")
                    semi_finished_col = cols.get("منتج نصف مصنع")

                    if not (name_ar_col and code_col and price_col):
                        messages.error(request, "تأكد أن ملف الإكسل يحتوي الأعمدة: الاسم بالعربي، كود تعريف المنتج، سعر البيع.")
                        return redirect("admin:costing_product_changelist")

                    default_unit, _ = Unit.objects.get_or_create(
                        name="وحدة", defaults={"abbreviation": "وحدة"}
                    )

                    def to_bool(val):
                        if isinstance(val, str):
                            v = val.strip().lower()
                            return v in ("1", "نعم", "yes", "y", "true", "صح")
                        return bool(val)

                    for _, row in df.iterrows():
                        code = str(row[code_col]).strip()

                        name_ar = str(row[name_ar_col]).strip() if not pd.isna(row[name_ar_col]) else ""
                        name_en = ""
                        if name_en_col and not pd.isna(row[name_en_col]):
                            name_en = str(row[name_en_col]).strip()

                        selling_price = row[price_col] if not pd.isna(row[price_col]) else 0

                        is_semi_finished = False
                        if semi_finished_col:
                            is_semi_finished = to_bool(row[semi_finished_col])

                        is_sellable = not is_semi_finished

                        Product.objects.update_or_create(
                            code=code,
                            defaults={
                                "name": name_ar,
                                "name_en": name_en,
                                "base_unit": default_unit,
                                "selling_price_per_unit": selling_price,
                                "is_sellable": is_sellable,
                                "is_semi_finished": is_semi_finished,
                            },
                        )

                    messages.success(request, "تم استيراد المنتجات النهائية من ملف الإكسل بنجاح.")
                    return redirect("admin:costing_product_changelist")

                except Exception as e:
                    messages.error(request, f"حدث خطأ أثناء قراءة الملف: {e}")
        else:
            form = ProductImportForm()

        context = {
            "form": form,
            "title": "استيراد المنتجات من إكسل",
        }
        return render(request, "admin/costing/product_import.html", context)

