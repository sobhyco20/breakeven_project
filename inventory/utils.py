from decimal import Decimal

from costing.models import BillOfMaterial, Product
from purchases.models import PurchaseSummaryLine
from sales.models import SalesSummaryLine  # عدّل الاسم حسب مشروعك
from .models import StockCount, StockCountType, InventoryIssue
from costing.models import BillOfMaterial, BOMItem, Product, RawMaterial

def _get_stock_count_qty(raw_material, period, count_type):
    from costing.models import Unit

    qs = StockCount.objects.filter(period=period, count_type=count_type)
    total = Decimal("0")
    for sc in qs:
        for line in sc.lines.filter(raw_material=raw_material):
            total += line.quantity
    return total


def _get_purchases_qty(raw_material, period):
    """الكمية المشتراة بوحدة الاستخدام (ingredient_unit)."""
    from costing.models import RawMaterial as RM

    rm = raw_material
    qs = PurchaseSummaryLine.objects.filter(
        raw_material=rm,
        summary__period=period,
    )

    total_storage_qty = Decimal("0")
    for line in qs:
        if line.quantity:
            total_storage_qty += line.quantity

    if total_storage_qty <= 0:
        return Decimal("0")

    # تحويل من وحدة التخزين إلى وحدة الاستخدام
    if rm.storage_to_ingredient_factor:
        return total_storage_qty * rm.storage_to_ingredient_factor

    return total_storage_qty


def _get_sales_consumption_qty(raw_material, period):
    """
    الكمية المنصرفة للمبيعات من هذه المادة الخام
    عن طريق تفكيك المبيعات إلى مواد خام باستخدام الـ BOM.
    (نسخة مبسطة: مستوى واحد من الـ BOM).
    """
    total = Decimal("0")

    # نفترض أن SalesSummaryLine فيها product و quantity
    lines = SalesSummaryLine.objects.filter(summary__period=period)

    for line in lines:
        product = line.product
        qty_sold = line.quantity or Decimal("0")
        if qty_sold <= 0:
            continue

        # نجيب الـ BOM الفعّال
        bom = product.boms.filter(is_active=True).first()
        if not bom:
            continue

        for item in bom.items.filter(raw_material=raw_material):
            # الكمية المطلوبة من الخام = كمية مبيعات المنتج × كمية الخام في الوصفة
            total += qty_sold * (item.quantity or Decimal("0"))

    return total


def _get_non_sales_issue_qty(raw_material, period):
    total = Decimal("0")
    issues = InventoryIssue.objects.filter(period=period)
    for issue in issues:
        for line in issue.lines.filter(raw_material=raw_material):
            total += line.quantity or Decimal("0")
    return total


def calculate_inventory_movement(raw_material, period):
    """
    ترجع قاموس يحوي كل مكونات معادلة المخزون لهذه المادة في فترة معيّنة.
    """
    opening = _get_stock_count_qty(raw_material, period, StockCountType.OPENING)
    closing = _get_stock_count_qty(raw_material, period, StockCountType.CLOSING)
    purchases = _get_purchases_qty(raw_material, period)
    sales_cons = _get_sales_consumption_qty(raw_material, period)
    non_sales_cons = _get_non_sales_issue_qty(raw_material, period)

    # معادلة المخزون
    difference = opening + purchases - sales_cons - non_sales_cons - closing

    return {
        "opening_qty": opening,
        "purchases_qty": purchases,
        "sales_consumption_qty": sales_cons,
        "non_sales_consumption_qty": non_sales_cons,
        "closing_qty": closing,
        "difference_qty": difference,
    }



def get_bom_tree(product, qty_factor=Decimal("1")):
    """
    ترجع شجرة كاملة للمنتج (Product) مع مكوناته:
    - مواد خام (RawMaterial) كأوراق نهائية.
    - منتجات نصف مصنّعة (Product) يتم فكّها بشكل متكرر.
    qty_factor = الكمية المطلوبة من المنتج النهائي.
    """
    tree = {
        "product": product,      # ممكن يكون Product أو RawMaterial في الأوراق
        "quantity": qty_factor,
        "components": [],
    }

    # لو الـ product مش Product (مثلاً RawMaterial) نرجعه كما هو كورقة
    if not isinstance(product, Product):
        return tree

    # نجيب الوصفة الفعّالة للمنتج
    bom = product.boms.filter(is_active=True).first()
    if not bom:
        # مفيش وصفة → نعتبره بدون مكونات (يبقى node أوراق)
        return tree

    # نمرّ على بنود الوصفة
    for item in bom.items.all():
        item_qty = qty_factor * (item.quantity or Decimal("0"))

        # 1) مادة خام مباشرة
        if item.raw_material:
            child = {
                "product": item.raw_material,   # هنا RawMaterial
                "quantity": item_qty,
                "components": [],
            }
            tree["components"].append(child)

        # 2) منتج نصف مصنع / منتج مكوّن
        elif item.component_product:
            subtree = get_bom_tree(item.component_product, qty_factor=item_qty)
            tree["components"].append(subtree)

        # لو لا خام ولا منتج، نتجاهله

    return tree


def flatten_bom_tree(tree, results=None):
    """
    ترجع ملخص نهائي لاستهلاك المواد الخام:
    { raw_material_id: total_qty }
    """
    if results is None:
        results = {}

    # لو مفيش مكونات → نتوقع أنها مادة خام
    if not tree["components"]:
        material = tree["product"]
        # لو المادة الخام فعلاً RawMaterial نخزنها
        if isinstance(material, RawMaterial):
            results[material.id] = results.get(material.id, 0) + tree["quantity"]
        # لو Product بدون BOM نطنّشها من الملخص
        return results

    # لو فيه مكونات → ننزل في الشجرة
    for comp in tree["components"]:
        flatten_bom_tree(comp, results)

    return results
def flatten_bom_tree_nodes(tree, results=None, level=0, parent=None):
    """
    ترجع قائمة بكل العقد (المنتج النهائي + النصف مصنع + المواد الخام)
    لاستعمالها في جدول تفصيلي.
    كل عنصر في النتائج:
    {
        "level": عمق في الشجرة,
        "product": الكائن (Product أو RawMaterial),
        "quantity": الكمية,
        "parent": الأب (Product أو RawMaterial أو None),
        "is_leaf": هل هو مادة خام/نهاية الشجرة
    }
    """
    if results is None:
        results = []

    node_info = {
        "level": level,
        "product": tree["product"],
        "quantity": tree["quantity"],
        "parent": parent,
        "is_leaf": not tree["components"],
    }
    results.append(node_info)

    for child in tree["components"]:
        flatten_bom_tree_nodes(child, results, level=level + 1, parent=tree["product"])

    return results

from costing.models import RawMaterial, Product  # تأكد أن الاستيرادات موجودة

def flatten_bom_tree_nodes(tree, results=None, level=0, parent=None):
    """
    ترجِع قائمة بكل العقد (المنتج النهائي + النصف مصنع + المواد الخام)
    لاستعمالها في جدول تفصيلي داخل التقرير.

    كل عنصر في النتائج:
    {
        "level":   مستوى العقدة داخل الشجرة (0 = المنتج النهائي),
        "product": الكائن (Product أو RawMaterial),
        "quantity": الكمية عند هذا المستوى,
        "parent":  الأب (Product أو RawMaterial أو None),
        "is_leaf": هل العقدة ورقة (مادة خام فعلية)
    }
    """
    if results is None:
        results = []

    node_info = {
        "level": level,
        "product": tree["product"],
        "quantity": tree["quantity"],
        "parent": parent,
        "is_leaf": not tree["components"],
    }
    results.append(node_info)

    for child in tree["components"]:
        flatten_bom_tree_nodes(child, results, level=level + 1, parent=tree["product"])

    return results
