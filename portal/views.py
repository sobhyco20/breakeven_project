# portal/views.py  (تعديل شامل + تنظيف + توحيد أسماء الدوال)

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Q

from costing.models import Product, Unit, BillOfMaterial, BOMItem, RawMaterial

from django.http import JsonResponse


from django.db import transaction, IntegrityError

def _embed(request) -> bool:
    return request.GET.get("embed") == "1"


@staff_member_required
def portal_home(request):
    """
    Portal الرئيسية: قائمة جانبية + iframe لعرض شاشات الإدخال.
    """
    sections = [
        {
            "key": "company",
            "title": "🏢 إعدادات الشركة",
            "items": [
                {"title": "إعدادات الشركة", "url": "/portal/company/?embed=1"},
            ],
        },
        {
            "key": "master",
            "title": "📦 البيانات الأساسية",
            "items": [
                {"title": "وحدات القياس", "url": "/portal/units/?embed=1"},
                {"title": "تحويل وحدات المواد", "url": "/portal/conversions/?embed=1"},
                {"title": "المواد الخام", "url": "/portal/raw-materials/?embed=1"},
                {"title": "المنتجات", "url": "/portal/products/?embed=1"},
                {"title": "الوصفات (BOM)", "url": "/portal/bom/?embed=1"},
            ],
        },
        {
            "key": "expenses",
            "title": "💸 المصروفات",
            "items": [
                {"title": "إدخال المصروفات", "url": "/portal/expenses/?embed=1"},
            ],
        },
        {
            "key": "periods",
            "title": "🗓 الفترات",
            "items": [
                {"title": "الفترات", "url": "/portal/periods/?embed=1"},
            ],
        },
    ]

    default_url = sections[0]["items"][0]["url"] if sections and sections[0].get("items") else "/portal/company/?embed=1"

    return render(request, "portal/home.html", {
        "embed": _embed(request),
        "sections": sections,
        "default_url": default_url,
        "page_title": "بوابة الإدخالات",
    })

# portal/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from costing.models import Unit, RawMaterial, Product

@staff_member_required
def home(request):
    return render(request, "portal/shell.html", {"embed": request.GET.get("embed") == "1"})

@staff_member_required
def company(request):
    return render(request, "portal/company.html", {"embed": request.GET.get("embed") == "1"})

@staff_member_required
def units(request):
    return render(request, "portal/units.html", {"embed": request.GET.get("embed") == "1"})

# portal/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from costing.models import Unit

@staff_member_required
def raw_materials(request):
    return render(request, "portal/raw_materials.html", {
        "embed": request.GET.get("embed") == "1",
        "units": Unit.objects.order_by("name"),
    })


from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from costing.models import Product, Unit 


def _d(v):
    try:
        return Decimal(str(v or "0"))
    except Exception:
        return Decimal("0")



from django.apps import apps

def _model_exists(app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None

from django.apps import apps
from costing.models import BillOfMaterial, BOMItem

def product_locked(p: Product) -> bool:
    # 🔒 1) حركة BOM
    if BillOfMaterial.objects.filter(product=p).exists():
        return True

    if BOMItem.objects.filter(component_product=p).exists():
        return True

    # 🔒 2) حركة مبيعات (SalesSummaryLine)
    SalesSummaryLine = apps.get_model("sales", "SalesSummaryLine")
    if SalesSummaryLine.objects.filter(product=p).exists():
        return True

    return False





@staff_member_required
def products_page(request):
    units = Unit.objects.all().order_by("name")
    return render(request, "portal/products.html", {"units": units})


@staff_member_required
@require_GET
def products_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = Product.objects.select_related("base_unit").all().order_by("code")
    if q:
        qs = qs.filter(code__icontains=q) | qs.filter(name__icontains=q) | qs.filter(name_en__icontains=q)

    rows = []
    for p in qs[:2000]:
        locked = product_locked(p)

        # ✅ تكلفة الوحدة من BOM (لو موجود)
        unit_cost = p.compute_unit_cost(period=None)  # ممكن تبعت period لاحقًا

        rows.append({
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "name_en": p.name_en or "",
            "base_unit_id": p.base_unit_id,
            "selling_price_per_unit": str(p.selling_price_per_unit or ""),
            "unit_cost": str(unit_cost or ""),   # ← تكلفة من BOM
            "locked": locked,
        })

    return JsonResponse({"ok": True, "rows": rows})

from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
@require_POST
@transaction.atomic
def products_api(request):

    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse(
            {"ok": False, "error": "انتهت الجلسة، أعد تحميل الصفحة"},
            status=403
        )

    action = request.POST.get("action") or ""

    if action == "delete":
        pid = request.POST.get("id") or ""
        if not pid:
            return JsonResponse({"ok": False, "error": "id مطلوب"}, status=400)
        p = get_object_or_404(Product, pk=pid)
        if product_locked(p):
            return JsonResponse({"ok": False, "error": "لا يمكن الحذف: المنتج عليه حركة"}, status=400)

        p.delete()
        return JsonResponse({"ok": True})

    if action == "save":
        pid = request.POST.get("id") or ""
        code = (request.POST.get("code") or "").strip()
        name = (request.POST.get("name") or "").strip()
        name_en = (request.POST.get("name_en") or "").strip()
        base_unit_id = request.POST.get("base_unit_id") or ""
        selling_price = request.POST.get("selling_price_per_unit") or ""

        if not code or not name:
            return JsonResponse({"ok": False, "error": "الكود والاسم العربي مطلوبين"}, status=400)
        if not base_unit_id:
            return JsonResponse({"ok": False, "error": "اختر وحدة المنتج"}, status=400)

        if pid:
            p = get_object_or_404(Product, pk=pid)
            if product_locked(p):
                return JsonResponse({"ok": False, "error": "ممنوع الحفظ: المنتج عليه حركة"}, status=400)

        else:
            p = Product()

        p.code = code
        p.name = name
        p.name_en = name_en or None
        p.base_unit_id = int(base_unit_id)

        p.selling_price_per_unit = _d(selling_price) if selling_price != "" else None

        p.save()
        return JsonResponse({"ok": True, "id": p.id})
    
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse(
            {"ok": False, "error": "انتهت الجلسة، أعد تحميل الصفحة"},
            status=403
        )

    return JsonResponse({"ok": False, "error": "action غير معروف"}, status=400)





@staff_member_required
def unit_conversions(request):
    rows = (RawMaterial.objects
            .select_related("storage_unit", "ingredient_unit")
            .order_by("sku", "name"))
    units = Unit.objects.order_by("name")
    return render(request, "portal/conversions.html", {
        "embed": request.GET.get("embed") == "1",
        "rows": rows,
        "units": units,
    })



# placeholders (لتجنب 404 حالياً)
@staff_member_required
def bom(request):
    return render(request, "portal/shell.html", {"embed": _embed(request), "page_title": "الوصفات (قريباً)"})


@staff_member_required
def expenses(request):
    return render(request, "portal/shell.html", {"embed": _embed(request), "page_title": "المصروفات (قريباً)"})


@staff_member_required
def periods(request):
    return render(request, "portal/shell.html", {"embed": _embed(request), "page_title": "الفترات (قريباً)"})


def products(request):
    return products_page(request)
# portal/views.py  (نسخة نظيفة + موحدة)

from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from costing.models import Product, Unit, BillOfMaterial, BOMItem, RawMaterial


def _embed(request) -> bool:
    return request.GET.get("embed") == "1"


def _d(v, default="0"):
    try:
        return Decimal(str(v if v not in (None, "") else default))
    except Exception:
        return Decimal(default)


# =========================
# Portal Home
# =========================
@staff_member_required
def portal_home(request):
    sections = [
        {
            "key": "company",
            "title": "🏢 إعدادات الشركة",
            "items": [{"title": "إعدادات الشركة", "url": "/portal/company/?embed=1"}],
        },
        {
            "key": "master",
            "title": "📦 البيانات الأساسية",
            "items": [
                {"title": "وحدات القياس", "url": "/portal/units/?embed=1"},
                {"title": "تحويل وحدات المواد", "url": "/portal/conversions/?embed=1"},
                {"title": "المواد الخام", "url": "/portal/raw-materials/?embed=1"},
                {"title": "المنتجات", "url": "/portal/products/?embed=1"},
                {"title": "الوصفات (BOM)", "url": "/portal/bom/?embed=1"},
            ],
        },
        {
            "key": "expenses",
            "title": "💸 المصروفات",
            "items": [{"title": "إدخال المصروفات", "url": "/portal/expenses/?embed=1"}],
        },
        {
            "key": "periods",
            "title": "🗓 الفترات",
            "items": [{"title": "الفترات", "url": "/portal/periods/?embed=1"}],
        },
    ]

    default_url = sections[0]["items"][0]["url"] if sections and sections[0].get("items") else "/portal/company/?embed=1"
    return render(request, "portal/home.html", {
        "embed": _embed(request),
        "sections": sections,
        "default_url": default_url,
        "page_title": "بوابة الإدخالات",
    })


# =========================
# Simple pages (placeholders)
# =========================
@staff_member_required
def company(request):
    return render(request, "portal/company.html", {"embed": _embed(request)})

@staff_member_required
def units(request):
    return render(request, "portal/units.html", {"embed": _embed(request)})

@staff_member_required
def bom(request):
    return render(request, "portal/shell.html", {"embed": _embed(request), "page_title": "الوصفات (قريباً)"})

@staff_member_required
def expenses(request):
    return render(request, "portal/shell.html", {"embed": _embed(request), "page_title": "المصروفات (قريباً)"})

@staff_member_required
def periods(request):
    return render(request, "portal/shell.html", {"embed": _embed(request), "page_title": "الفترات (قريباً)"})


# =========================
# RAW MATERIALS
# =========================
@staff_member_required
def raw_materials(request):
    return render(request, "portal/raw_materials.html", {
        "embed": _embed(request),
        "units": Unit.objects.order_by("name"),
    })


# =========================
# CONVERSIONS
# =========================
@staff_member_required
def unit_conversions(request):
    rows = (RawMaterial.objects
            .select_related("storage_unit", "ingredient_unit")
            .order_by("sku", "name"))
    units = Unit.objects.order_by("name")
    return render(request, "portal/conversions.html", {
        "embed": _embed(request),
        "rows": rows,
        "units": units,
    })


# =========================
# PRODUCTS (UI + API)
# =========================
def product_locked(p: Product) -> bool:
    # عليه حركة لو له BOM أو مستخدم كمكوّن في BOM آخر
    if BillOfMaterial.objects.filter(product=p).exists():
        return True
    if BOMItem.objects.filter(component_product=p).exists():
        return True
    return False


@staff_member_required
def products(request):
    return render(request, "portal/products.html", {
        "embed": _embed(request),
        "units": Unit.objects.order_by("name"),
    })


@staff_member_required
@require_GET
def products_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = Product.objects.select_related("base_unit").all().order_by("code")
    if q:
        qs = qs.filter(
            Q(code__icontains=q) | Q(name__icontains=q) | Q(name_en__icontains=q)
        )

    rows = []
    for p in qs[:2000]:
        locked = product_locked(p)

        unit_cost = ""
        try:
            v = p.compute_unit_cost(period=None)
            unit_cost = str(v) if v is not None else ""
        except Exception:
            unit_cost = ""

        rows.append({
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "name_en": p.name_en or "",
            "base_unit_id": p.base_unit_id,
            "selling_price_per_unit": str(p.selling_price_per_unit or ""),
            "unit_cost": unit_cost,  # ✅ محسوبة من BOM
            "locked": locked,
        })

    return JsonResponse({"ok": True, "rows": rows})


@staff_member_required
@require_POST
@transaction.atomic
def products_api(request):
    action = (request.POST.get("action") or "").strip()

    if action == "delete":
        pid = (request.POST.get("id") or "").strip()
        if not pid:
            return JsonResponse({"ok": False, "error": "id مطلوب"}, status=400)

        p = get_object_or_404(Product, pk=pid)
        if product_locked(p):
            return JsonResponse({"ok": False, "error": "لا يمكن الحذف: المنتج عليه حركة (مرتبط بوصفة BOM)."}, status=400)

        p.delete()
        return JsonResponse({"ok": True})

    if action == "save":
        pid = (request.POST.get("id") or "").strip()
        code = (request.POST.get("code") or "").strip()
        name = (request.POST.get("name") or "").strip()
        name_en = (request.POST.get("name_en") or "").strip()
        base_unit_id = (request.POST.get("base_unit_id") or "").strip()
        selling_price = (request.POST.get("selling_price_per_unit") or "").strip()

        if not code:
            return JsonResponse({"ok": False, "error": "الكود مطلوب"}, status=400)
        if not name:
            return JsonResponse({"ok": False, "error": "الاسم العربي مطلوب"}, status=400)
        if not base_unit_id:
            return JsonResponse({"ok": False, "error": "اختر وحدة المنتج"}, status=400)

        if pid:
            p = get_object_or_404(Product, pk=pid)
            # ✅ لو تريد منع التعديل عند الحركة (مثل الخامات):
            if product_locked(p):
                return JsonResponse({"ok": False, "error": "ممنوع الحفظ: المنتج عليه حركة"}, status=400)
        else:
            p = Product()

        p.code = code
        p.name = name
        p.name_en = name_en or None
        p.base_unit_id = int(base_unit_id)
        p.selling_price_per_unit = _d(selling_price, "0") if selling_price != "" else None
        p.save()

        # رجّع التكلفة بعد الحفظ
        unit_cost = ""
        try:
            v = p.compute_unit_cost(period=None)
            unit_cost = str(v) if v is not None else ""
        except Exception:
            unit_cost = ""

        return JsonResponse({"ok": True, "id": p.id, "unit_cost": unit_cost, "locked": product_locked(p)})

    return JsonResponse({"ok": False, "error": "action غير معروف"}, status=400)




from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def expenses_definitions(request):
    embed = request.GET.get("embed") == "1"
    return render(request, "portal/expenses_definitions.html", {"embed": embed})


from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def expenses_entry(request):
    embed = request.GET.get("embed") == "1"
    return render(request, "portal/expenses_entry.html", {"embed": embed})




from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction

from expenses.models import Period, ExpenseBatch
# لو عندك نماذج حركة أخرى ضيفها هنا:
# from sales.models import SalesSummary
# from purchases.models import PurchaseSummary
# from inventory.models import StockMove

@staff_member_required
def periods_view(request):
    embed = request.GET.get("embed") == "1"
    return render(request, "portal/periods.html", {"embed": embed})

def _has_period_activity(period: Period) -> bool:
    """
    ✅ لو الفترة عليها حركة: اقفل التعديل/الحذف/فتح-قفل حسب رغبتك.
    عدّل المنطق حسب موديلاتك.
    """
    # مصروفات
    if ExpenseBatch.objects.filter(period=period).exists():
        # وجود Batch يعني عليها حركة
        return True

    # أمثلة لو عندك موديلات أخرى:
    # if SalesSummary.objects.filter(period=period).exists(): return True
    # if PurchaseSummary.objects.filter(period=period).exists(): return True
    # if StockMove.objects.filter(period=period).exists(): return True

    return False

@require_GET
@staff_member_required
def api_periods_list(request):
    periods = Period.objects.order_by("-year", "-month")
    rows = []
    for p in periods:
        has_activity = _has_period_activity(p)
        rows.append({
            "id": p.id,
            "year": p.year,
            "month": p.month,
            "label": f"{p.year}-{p.month:02d}",
            "is_closed": bool(p.is_closed),
            "has_activity": bool(has_activity),
        })
    return JsonResponse({"ok": True, "rows": rows})

@require_POST
@staff_member_required
@transaction.atomic
def api_periods_toggle(request):
    pid = request.POST.get("id")
    p = Period.objects.filter(id=pid).first()
    if not p:
        return JsonResponse({"ok": False, "error": "الفترة غير موجودة"}, status=404)

    # ✅ ممنوع تغيير حالة الفترة لو عليها حركة (حسب طلبك)
    if _has_period_activity(p):
        return JsonResponse({"ok": False, "error": "لا يمكن تعديل حالة الفترة لأنها تحتوي على حركة/بيانات."}, status=400)

    p.is_closed = not p.is_closed
    p.save(update_fields=["is_closed"])
    return JsonResponse({"ok": True, "id": p.id, "is_closed": p.is_closed})





def _has_period_activity(period: Period) -> bool:
    # ✅ عدّل لاحقًا لإضافة sales/purchases/inventory
    return ExpenseBatch.objects.filter(period=period).exists()



@require_POST
@staff_member_required
@transaction.atomic
def api_periods_create(request):
    """
    ✅ إنشاء فترة جديدة من البورتال
    """
    year = int(request.POST.get("year") or 0)
    month = int(request.POST.get("month") or 0)

    if year < 2000 or year > 2100:
        return JsonResponse({"ok": False, "error": "سنة غير صحيحة"}, status=400)
    if month < 1 or month > 12:
        return JsonResponse({"ok": False, "error": "شهر غير صحيح"}, status=400)

    try:
        obj, created = Period.objects.get_or_create(
            year=year, month=month,
            defaults={"is_closed": False},
        )
    except IntegrityError:
        return JsonResponse({"ok": False, "error": "تعذر إنشاء الفترة (قد تكون موجودة)."}, status=400)

    return JsonResponse({"ok": True, "created": created, "id": obj.id})


@require_POST
@staff_member_required
@transaction.atomic
def api_periods_update(request):
    """
    ✅ تعديل السنة/الشهر (ممنوع لو عليها حركة)
    """
    pid = request.POST.get("id")
    year = int(request.POST.get("year") or 0)
    month = int(request.POST.get("month") or 0)

    p = Period.objects.filter(id=pid).first()
    if not p:
        return JsonResponse({"ok": False, "error": "الفترة غير موجودة"}, status=404)

    if _has_period_activity(p):
        return JsonResponse({"ok": False, "error": "ممنوع التعديل: الفترة عليها حركة."}, status=400)

    if year < 2000 or year > 2100:
        return JsonResponse({"ok": False, "error": "سنة غير صحيحة"}, status=400)
    if month < 1 or month > 12:
        return JsonResponse({"ok": False, "error": "شهر غير صحيح"}, status=400)

    # منع تكرار نفس (year, month)
    exists = Period.objects.exclude(id=p.id).filter(year=year, month=month).exists()
    if exists:
        return JsonResponse({"ok": False, "error": "هذه الفترة موجودة بالفعل."}, status=400)

    p.year = year
    p.month = month
    p.save(update_fields=["year", "month"])
    return JsonResponse({"ok": True})


@require_POST
@staff_member_required
@transaction.atomic
def api_periods_delete(request):
    """
    ✅ حذف الفترة (ممنوع لو عليها حركة)
    """
    pid = request.POST.get("id")
    p = Period.objects.filter(id=pid).first()
    if not p:
        return JsonResponse({"ok": False, "error": "الفترة غير موجودة"}, status=404)

    if _has_period_activity(p):
        return JsonResponse({"ok": False, "error": "ممنوع الحذف: الفترة عليها حركة."}, status=400)

    # ✅ لو عندك علاقات أخرى تمنع الحذف هتطلع IntegrityError طبيعي
    try:
        p.delete()
    except Exception:
        return JsonResponse({"ok": False, "error": "تعذر الحذف (ربما مرتبطة ببيانات أخرى)."}, status=400)

    return JsonResponse({"ok": True})


@require_POST
@staff_member_required
@transaction.atomic
def api_periods_toggle_close(request):
    """
    ✅ إغلاق / فتح
    (حسب طلبك: ممنوع لو عليها حركة)
    """
    pid = request.POST.get("id")
    p = Period.objects.filter(id=pid).first()
    if not p:
        return JsonResponse({"ok": False, "error": "الفترة غير موجودة"}, status=404)

    if _has_period_activity(p):
        return JsonResponse({"ok": False, "error": "ممنوع تغيير الحالة: الفترة عليها حركة."}, status=400)

    p.is_closed = not p.is_closed
    p.save(update_fields=["is_closed"])
    return JsonResponse({"ok": True, "is_closed": p.is_closed})


from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
import re

from expenses.models import Period, ExpenseBatch, ExpenseLine, ExpenseItem

def _period_from_request(request):
    """
    يقبل:
      ?period=12  (id)
      ?period_id=12
      ?period=2026-11  (year-month)
    """
    raw = (request.GET.get("period") or request.GET.get("period_id") or "").strip()
    if not raw:
        raise ValidationError("لم يتم إرسال الفترة.")

    # 1) id رقمي
    if raw.isdigit():
        p = Period.objects.filter(pk=int(raw)).first()
        if not p:
            raise ValidationError("الفترة غير موجودة (id).")
        return p

    # 2) year-month مثل 2026-11
    m = re.match(r"^\s*(\d{4})-(\d{1,2})\s*$", raw)
    if m:
        y = int(m.group(1)); mo = int(m.group(2))
        p = Period.objects.filter(year=y, month=mo).first()
        if not p:
            raise ValidationError("الفترة غير موجودة (YYYY-MM).")
        return p

    raise ValidationError("قيمة الفترة غير صحيحة. استخدم id أو YYYY-MM.")


def _ensure_batch_and_lines(period: Period) -> ExpenseBatch:
    batch, _ = ExpenseBatch.objects.get_or_create(period=period)
    # ضمان وجود سطر لكل بند
    existing = set(ExpenseLine.objects.filter(batch=batch).values_list("item_id", flat=True))
    to_create = []
    for it in ExpenseItem.objects.filter(is_active=True):
        if it.id not in existing:
            to_create.append(ExpenseLine(batch=batch, item=it, amount=Decimal("0"), notes=""))
    if to_create:
        ExpenseLine.objects.bulk_create(to_create)
    return batch


def _totals_for_batch(batch: ExpenseBatch):
    # إجماليات حسب OP/SA/AD
    qs = ExpenseLine.objects.filter(batch=batch).select_related("item__category")
    totals = {"OP": Decimal("0"), "SA": Decimal("0"), "AD": Decimal("0")}
    for ln in qs:
        nature = getattr(ln.item.category, "nature", None)
        if nature in totals:
            totals[nature] += (ln.amount or Decimal("0"))
    totals["ALL"] = totals["OP"] + totals["SA"] + totals["AD"]
    # ترجيع كـ string
    return {k: f"{v:.2f}" for k, v in totals.items()}


@transaction.atomic
def api_expenses_entry_load(request):
    try:
        period = _period_from_request(request)
        batch = _ensure_batch_and_lines(period)

        # تجهيز البيانات مقسمة
        lines = (
            ExpenseLine.objects
            .filter(batch=batch)
            .select_related("item", "item__category")
            .order_by("item__category__nature", "item__code")
        )

        groups = {"OP": {"code":"OP","rows":[]}, "SA":{"code":"SA","rows":[]}, "AD":{"code":"AD","rows":[]}}
        for ln in lines:
            cat = ln.item.category
            code = getattr(cat, "nature", None)
            if code not in groups:
                continue
            groups[code]["rows"].append({
                "line_id": ln.id,
                "item_code": ln.item.code,
                "item_name": ln.item.name,
                "category": f"{cat.code} - {cat.name}",
                "amount": f"{(ln.amount or Decimal('0')):.2f}",
            })

        return JsonResponse({
            "ok": True,
            "period": {
                "id": period.id,
                "label": f"{period.year}-{period.month:02d}",
                "is_closed": bool(period.is_closed),
            },
            "totals": _totals_for_batch(batch),
            "groups": groups,
        })

    except ValidationError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    except Exception as e:
        # بدل 500 HTML
        return JsonResponse({"ok": False, "error": f"خطأ داخلي: {e}"}, status=500)


from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from costing.models import BillOfMaterial

@staff_member_required
def portal_bom(request):
    bom_id = request.GET.get("bom_id") or ""
    boms = BillOfMaterial.objects.select_related("product").order_by("product__code")
    return render(request, "portal/bom_drag.html", {
        "boms": boms,
        "bom_id": str(bom_id),
        "embed": request.GET.get("embed", ""),
    })


# portal/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from costing.models import BillOfMaterial, Product

@require_GET
def api_bom_open_by_product(request, product_id):
    bom = BillOfMaterial.objects.filter(product_id=product_id).order_by("-id").first()
    created = False
    if not bom:
      # لو تحب: أنشئ BOM جديد تلقائيًا
      bom = BillOfMaterial.objects.create(product_id=product_id, name="")
      created = True
    return JsonResponse({"bom_id": bom.id, "created": created})


# portal/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from expenses.models import Period

@staff_member_required
def portal_stockcount(request):
    """
    شاشة إدخال الجرد داخل Portal iframe
    """
    embed = request.GET.get("embed") == "1"
    periods = Period.objects.order_by("year", "month")

    period_id = request.GET.get("period") or ""
    count_type = (request.GET.get("type") or "opening").strip().lower()
    if count_type not in ("opening", "closing"):
        count_type = "opening"

    # default period: أول فترة عندك (أقدم) مثل أسلوبك
    period = Period.objects.filter(id=period_id).first() if period_id else periods.first()

    return render(request, "portal/stockcount_entry.html", {
        "embed": embed,
        "periods": periods,
        "period": period,
        "count_type": count_type,
        "page_title": "📦 إدخال الجرد",
    })

# portal/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from expenses.models import Period

@staff_member_required
def stockcount(request):
    embed = request.GET.get("embed") == "1"
    periods = Period.objects.order_by("year", "month")

    # ✅ نوع الجرد
    count_type = (request.GET.get("type") or "opening").strip().lower()
    if count_type not in ("opening", "closing"):
        count_type = "opening"

    # ✅ الفترة
    period_id = request.GET.get("period")
    if not period_id:
        p = periods.first()
        if not p:
            # لا توجد فترات
            return render(request, "portal/stockcount_entry.html", {
                "embed": embed,
                "periods": [],
                "period": None,
                "count_type": count_type,
                "page_title": "📦 إدخال الجرد",
            })
        # 🔁 redirect لضمان وجود period في الرابط
        url = f"/portal/stockcount/?embed={'1' if embed else '0'}&type={count_type}&period={p.id}"
        return redirect(url)

    period = Period.objects.filter(id=period_id).first()

    return render(request, "portal/stockcount_entry.html", {
        "embed": embed,
        "periods": periods,
        "period": period,
        "count_type": count_type,
        "page_title": "📦 إدخال الجرد",
    })

# portal/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from expenses.models import Period


def get_default_period():
    # اجعل الافتراضي أقدم فترة (مثلاً 1-2025) لو موجودة
    return Period.objects.order_by("year", "month").first()


@staff_member_required
def portal_sales_entry(request):
    embed = request.GET.get("embed") == "1"

    periods = Period.objects.order_by("year", "month")
    period_id = request.GET.get("period")
    period = Period.objects.filter(id=period_id).first() if period_id else None
    period = period or get_default_period()

    return render(request, "portal/sales_entry.html", {
        "embed": embed,
        "periods": periods,
        "period": period,
    })

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from expenses.models import Period

def get_default_period():
    return Period.objects.order_by("year", "month").first()

@staff_member_required
def sales_entry(request):
    embed = request.GET.get("embed") == "1"
    periods = Period.objects.order_by("year", "month")
    period_id = request.GET.get("period") or None
    period = Period.objects.filter(id=period_id).first() if period_id else None
    period = period or get_default_period()

    return render(request, "portal/sales_entry.html", {
        "embed": embed,
        "periods": periods,
        "period": period,
    })


# portal/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from expenses.models import Period

def get_default_period():
    return Period.objects.order_by("year", "month").first()

@staff_member_required
def portal_purchases_entry(request):
    embed = request.GET.get("embed") == "1"
    periods = Period.objects.order_by("year", "month")

    period_id = request.GET.get("period")
    period = Period.objects.filter(id=period_id).first() if period_id else None
    period = period or get_default_period()

    return render(request, "portal/purchases_entry.html", {
        "embed": embed,
        "periods": periods,
        "period": period,
    })
