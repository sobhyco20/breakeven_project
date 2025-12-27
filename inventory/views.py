# inventory/views.py
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404

from expenses.models import Period
from costing.models import RawMaterial
from purchases.models import PurchaseSummaryLine
from inventory.models import StockCount, StockCountLine, InventoryIssueLine
from sales.models import SalesConsumptionSummary, SalesConsumption
# inventory/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from costing.models import Product

from .utils import get_bom_tree, flatten_bom_tree





def _to_storage_qty(raw, qty, unit):
    """
    تحويل الكمية إلى *وحدة التخزين* للمادة الخام.
    لو:
      - الوحدة = وحدة التخزين => نرجع الكمية كما هي
      - الوحدة = وحدة الاستخدام => نقسم على معامل التحويل
      - غير ذلك => نرجع الكمية كما هي (حالة استثنائية)
    """
    if qty is None:
        return Decimal("0")

    qty = Decimal(qty)
    factor = raw.storage_to_ingredient_factor or Decimal("1")

    if raw.storage_unit_id and unit and unit.id == raw.storage_unit_id:
        return qty

    if raw.ingredient_unit_id and unit and unit.id == raw.ingredient_unit_id and factor:
        return qty / factor

    # fallback
    return qty


def materials_period_report(request):
    # كل الفترات للاختيار من القائمة
    periods = Period.objects.order_by("-start_date")

    period_id = request.GET.get("period")
    period = None
    rows = []

    if period_id:
        period = get_object_or_404(Period, id=period_id)

        # قواميس تجميع لكل مادة خام بالوحدة الكبيرة
        opening = {}          # رصيد أول الفترة
        closing = {}          # رصيد آخر الفترة
        purchases = {}        # مشتريات الفترة
        issue_sales = {}      # المنصرف للمبيعات
        issue_others = {}     # المنصرف لأغراض أخرى

        # ---------- 1) جرد أول الفترة ----------
        sc_opening = StockCount.objects.filter(period=period, type="opening").first()
        if sc_opening:
            lines = (
                StockCountLine.objects
                .filter(stock_count=sc_opening, raw_material__isnull=False)
                .select_related("raw_material", "unit")
            )
            for line in lines:
                raw = line.raw_material
                qty_storage = _to_storage_qty(raw, line.quantity, line.unit)
                opening[raw.id] = opening.get(raw.id, Decimal("0")) + qty_storage

        # ---------- 2) جرد آخر الفترة ----------
        sc_closing = StockCount.objects.filter(period=period, type="closing").first()
        if sc_closing:
            lines = (
                StockCountLine.objects
                .filter(stock_count=sc_closing, raw_material__isnull=False)
                .select_related("raw_material", "unit")
            )
            for line in lines:
                raw = line.raw_material
                qty_storage = _to_storage_qty(raw, line.quantity, line.unit)
                closing[raw.id] = closing.get(raw.id, Decimal("0")) + qty_storage

        # ---------- 3) مشتريات الفترة ----------
        purchase_lines = (
            PurchaseSummaryLine.objects
            .filter(summary__period=period)
            .select_related("raw_material", "purchase_unit")
        )
        for line in purchase_lines:
            raw = line.raw_material
            if not raw:
                continue
            # نفترض أن كمية الشراء بالفعل بوحدة التخزين
            qty_storage = Decimal(line.quantity or 0)
            purchases[raw.id] = purchases.get(raw.id, Decimal("0")) + qty_storage

        # ---------- 4) المنصرف لأغراض أخرى ----------
        issue_lines = (
            InventoryIssueLine.objects
            .filter(inventory_issue__period=period)
            .select_related("raw_material", "unit", "inventory_issue")
        )
        for line in issue_lines:
            raw = line.raw_material
            if not raw:
                continue
            qty_storage = _to_storage_qty(raw, line.quantity, line.unit)
            issue_others[raw.id] = issue_others.get(raw.id, Decimal("0")) + qty_storage

        # ---------- 5) المنصرف للمبيعات (من جدول الاستهلاك) ----------
        cons_lines = (
            SalesConsumption.objects
            .filter(summary__period=period)
            .select_related("raw_material")
        )
        for line in cons_lines:
            raw = line.raw_material
            if not raw:
                continue
            # quantity_consumed هنا بالوحدة الصغيرة -> نحول للوحدة الكبيرة
            qty_storage = _to_storage_qty(raw, line.quantity_consumed, raw.ingredient_unit)
            issue_sales[raw.id] = issue_sales.get(raw.id, Decimal("0")) + qty_storage

        # ---------- 6) بناء الصفوف ----------
        # كل المواد التي ظهر لها أي حركة
        material_ids = set(
            list(opening.keys())
            + list(closing.keys())
            + list(purchases.keys())
            + list(issue_sales.keys())
            + list(issue_others.keys())
        )

        materials = RawMaterial.objects.filter(id__in=material_ids).select_related("storage_unit")

        for raw in materials:
            open_qty = opening.get(raw.id, Decimal("0"))
            close_qty = closing.get(raw.id, Decimal("0"))
            purch_qty = purchases.get(raw.id, Decimal("0"))
            sales_qty = issue_sales.get(raw.id, Decimal("0"))
            other_qty = issue_others.get(raw.id, Decimal("0"))

            # المعادلة النظرية = أول + مشتريات - (مبيعات + أغراض أخرى)
            theoretical = open_qty + purch_qty - (sales_qty + other_qty)

            # فرق الكمية = جرد آخر الفترة - المعادلة النظرية
            diff_qty = close_qty - theoretical

            # تكلفة الوحدة من المشتريات/المخزون (أنت عندك دوال جاهزة في RawMaterial)
            unit_cost = raw.get_cost_from_purchases(period=period) or raw.get_cost_per_ingredient_unit(period=period)
            # نحولها إلى تكلفة وحدة التخزين إن كانت بوحدة الاستخدام
            if unit_cost and raw.storage_to_ingredient_factor:
                unit_cost = unit_cost * raw.storage_to_ingredient_factor

            diff_value = None
            if unit_cost is not None:
                diff_value = diff_qty * Decimal(unit_cost)

            rows.append({
                "raw": raw,
                "unit": raw.storage_unit or raw.ingredient_unit,
                "open_qty": open_qty,
                "purch_qty": purch_qty,
                "sales_qty": sales_qty,
                "other_qty": other_qty,
                "close_qty": close_qty,
                "theoretical": theoretical,
                "diff_qty": diff_qty,
                "unit_cost": unit_cost,
                "diff_value": diff_value,
            })

    context = {
        "periods": periods,
        "selected_period": period,
        "rows": rows,
    }
    return render(request, "admin/inventory/materials_period_report.html", context)



from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from costing.models import Product, RawMaterial
from .utils import get_bom_tree, flatten_bom_tree, flatten_bom_tree_nodes  # <-- أضف flatten_bom_tree_nodes


@login_required
def bom_tree_report_view(request):
    product_id = request.GET.get("product")
    quantity = request.GET.get("qty", "1")

    selected_product = None
    tree = None
    flat_summary = []
    node_rows = []   # جدول تفصيلي
    qty = 1

    # المنتجات النهائية (القابلة للبيع)
    products = Product.objects.filter(is_sellable=True).order_by("name")

    if product_id:
        selected_product = get_object_or_404(Product, pk=product_id)

        try:
            qty = Decimal(str(quantity))
        except Exception:
            qty = Decimal("1")

        # بناء الشجرة
        tree = get_bom_tree(selected_product, qty_factor=qty)

        # ملخص المواد الخام
        flat_dict = flatten_bom_tree(tree)
        raw_materials = RawMaterial.objects.filter(id__in=flat_dict.keys())

        flat_summary = [
            {
                "material": rm,
                "quantity": flat_dict[rm.id],
            }
            for rm in raw_materials
        ]
        flat_summary.sort(key=lambda x: x["material"].name)

        # جدول تفصيلي لكل المكوّنات
        node_rows = flatten_bom_tree_nodes(tree)

    context = {
        "products": products,
        "selected_product": selected_product,
        "quantity": qty,
        "tree": tree,
        "flat_summary": flat_summary,
        "node_rows": node_rows,       # مهم
    }
    return render(request, "bom_tree_report.html", context)
