# pricing/api.py
from decimal import Decimal, ROUND_HALF_UP
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_http_methods, require_GET
from django.db.models import Q

from costing.models import Product
from expenses.models import Period

# =========================
# Constants & Helpers
# =========================
D0 = Decimal("0")
HUND = Decimal("100")
MONEY_Q = Decimal("0.01")


def d(v) -> Decimal:
    try:
        return Decimal(str(v or "0"))
    except Exception:
        return D0


def money(v) -> Decimal:
    return d(v).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def pct(n, den):
    """safe percentage: n/den*100 (returns Decimal or None)"""
    n = d(n)
    den = d(den)
    if den <= 0:
        return None
    return (n / den * HUND)


def get_period(period_id):
    if period_id:
        p = Period.objects.filter(id=period_id).first()
        if p:
            return p
    # ✅ الافتراضي: آخر فترة
    return Period.objects.order_by("year", "month").last()


# =========================
# 1) Dashboard Data (All Products)
# =========================
@staff_member_required
def pricing_dashboard_data(request):
    period = get_period(request.GET.get("period"))

    mode = request.GET.get("mode", "all")  # all | sell | internal
    q = (request.GET.get("q") or "").strip()

    markup_sell = d(request.GET.get("markup_sell") or "60")
    markup_internal = d(request.GET.get("markup_internal") or "20")

    opex_percent = d(request.GET.get("opex_percent") or "0")
    discount_percent = d(request.GET.get("discount_percent") or "0")
    vat_percent = d(request.GET.get("vat_percent") or "0")
    min_price = d(request.GET.get("min_price") or "0")

    products = Product.objects.filter(is_sellable=True, is_semi_finished=False).order_by("code")

    if mode == "sell":
        products = products.exclude(code__istartswith="SF-")
    elif mode == "internal":
        products = products.filter(code__istartswith="SF-")

    if q:
        products = products.filter(Q(name__icontains=q) | Q(code__icontains=q))

    rows = []

    totals = {
        "count": 0,

        "sum_cost": D0,
        "sum_current_sales": D0,
        "sum_suggested_sales": D0,

        "sum_gross_profit_current": D0,
        "sum_gross_profit_suggested": D0,

        "sum_net_profit_current": D0,
        "sum_net_profit_suggested": D0,

        "sum_delta_price": D0,
        "sum_delta_profit": D0,

        "avg_current_margin": None,     # weighted
        "avg_suggested_margin": None,   # weighted
    }

    total_current_sales_for_margin = D0
    total_suggested_sales_for_margin = D0
    total_current_gross_for_margin = D0
    total_suggested_gross_for_margin = D0

    for p in products:
        bom = p.get_active_bom()
        cost = (getattr(bom, "unit_cost_final", None) if bom else None) or p.compute_unit_cost(period=period)
        cost = d(cost)

        current_price = d(p.selling_price_per_unit)

        is_internal = str(p.code).upper().startswith("SF-")
        mk = markup_internal if is_internal else markup_sell

        suggested = cost * (Decimal("1") + mk / HUND)

        if discount_percent > 0:
            suggested = suggested * (Decimal("1") - discount_percent / HUND)

        if min_price and suggested < min_price:
            suggested = min_price

        suggested_with_vat = suggested * (Decimal("1") + vat_percent / HUND) if vat_percent else suggested

        # profits
        gross_profit_current = (current_price - cost) if current_price > 0 else D0
        gross_profit_suggested = (suggested - cost) if suggested > 0 else D0

        # OPEX as % of price
        opex_amount_current = (current_price * (opex_percent / HUND)) if (opex_percent and current_price > 0) else D0
        opex_amount_suggested = (suggested * (opex_percent / HUND)) if (opex_percent and suggested > 0) else D0

        net_profit_current = gross_profit_current - opex_amount_current
        net_profit_suggested = gross_profit_suggested - opex_amount_suggested

        # deltas
        delta_price = suggested - current_price
        delta_price_pct = pct(delta_price, current_price)

        delta_profit = gross_profit_suggested - gross_profit_current
        delta_profit_pct = pct(delta_profit, gross_profit_current)

        # margins
        current_margin = pct(gross_profit_current, current_price) if current_price > 0 else None
        suggested_margin = pct(gross_profit_suggested, suggested) if suggested > 0 else None

        # badge
        if net_profit_suggested <= 0:
            badge = "red"
        elif suggested_margin is not None and suggested_margin >= Decimal("30"):
            badge = "green"
        elif suggested_margin is not None and suggested_margin >= Decimal("15"):
            badge = "yellow"
        else:
            badge = "red"

        row = {
            "code": p.code,
            "name": p.name,
            "type": "INTERNAL" if is_internal else "SELL",

            "cost": float(money(cost)),

            "current_price": float(money(current_price)),
            "gross_profit_current": float(money(gross_profit_current)),
            "net_profit_current": float(money(net_profit_current)),
            "current_margin_percent": float(money(current_margin)) if current_margin is not None else None,

            "suggested_price": float(money(suggested)),
            "suggested_price_vat": float(money(suggested_with_vat)),
            "gross_profit_suggested": float(money(gross_profit_suggested)),
            "net_profit_suggested": float(money(net_profit_suggested)),
            "suggested_margin_percent": float(money(suggested_margin)) if suggested_margin is not None else None,

            "delta_price": float(money(delta_price)),
            "delta_price_pct": float(money(delta_price_pct)) if delta_price_pct is not None else None,

            "delta_profit": float(money(delta_profit)),
            "delta_profit_pct": float(money(delta_profit_pct)) if delta_profit_pct is not None else None,

            "markup_percent": float(money(mk)),
            "opex_percent": float(money(opex_percent)),
            "discount_percent": float(money(discount_percent)),
            "vat_percent": float(money(vat_percent)),
            "min_price": float(money(min_price)),

            "badge": badge,
        }

        rows.append(row)

        totals["count"] += 1
        totals["sum_cost"] += cost
        totals["sum_current_sales"] += current_price
        totals["sum_suggested_sales"] += suggested
        totals["sum_gross_profit_current"] += gross_profit_current
        totals["sum_gross_profit_suggested"] += gross_profit_suggested
        totals["sum_net_profit_current"] += net_profit_current
        totals["sum_net_profit_suggested"] += net_profit_suggested
        totals["sum_delta_price"] += delta_price
        totals["sum_delta_profit"] += delta_profit

        # weighted avg margins
        if current_price > 0:
            total_current_sales_for_margin += current_price
            total_current_gross_for_margin += gross_profit_current

        if suggested > 0:
            total_suggested_sales_for_margin += suggested
            total_suggested_gross_for_margin += gross_profit_suggested

    totals["avg_current_margin"] = (
        float(money(pct(total_current_gross_for_margin, total_current_sales_for_margin)))
        if total_current_sales_for_margin > 0 else None
    )
    totals["avg_suggested_margin"] = (
        float(money(pct(total_suggested_gross_for_margin, total_suggested_sales_for_margin)))
        if total_suggested_sales_for_margin > 0 else None
    )

    payload = {
        "period": {"id": period.id if period else None, "label": str(period) if period else ""},
        "rows": rows,
        "totals": {k: (float(money(v)) if isinstance(v, Decimal) else v) for k, v in totals.items()},
    }
    return JsonResponse(payload, safe=False)


# =========================
# 2) Single Product Pricing Calc (dynamic form)
# =========================
@staff_member_required
@require_GET
def pricing_product_calc(request):
    product_id = request.GET.get("product")
    if not product_id:
        return JsonResponse({"ok": False, "error": "product is required"}, status=400)

    period = get_period(request.GET.get("period"))
    p = Product.objects.filter(id=product_id).first()
    if not p:
        return JsonResponse({"ok": False, "error": "product not found"}, status=404)

    # Inputs (policy)
    markup_sell = d(request.GET.get("markup_sell") or "60")
    target_margin = d(request.GET.get("target_margin") or "0")
    custom_price = d(request.GET.get("custom_price") or "0")

    opex_percent = d(request.GET.get("opex_percent") or "0")
    opex_unit = d(request.GET.get("opex_unit") or "0")

    discount_percent = d(request.GET.get("discount_percent") or "0")
    vat_percent = d(request.GET.get("vat_percent") or "0")
    min_price = d(request.GET.get("min_price") or "0")

    fixed_cost_total = d(request.GET.get("fixed_cost_total") or "0")

    # COST
    bom = p.get_active_bom()
    cost = (getattr(bom, "unit_cost_final", None) if bom else None) or p.compute_unit_cost(period=period)
    cost = d(cost)

    current_price = d(p.selling_price_per_unit)

    # Suggested price (priority order)
    # 1) base from markup
    suggested = cost * (Decimal("1") + (markup_sell / HUND))

    # 2) target margin overrides markup (if valid)
    # margin% = (price - cost)/price => price = cost / (1 - margin)
    if target_margin and (Decimal("0") < target_margin < Decimal("100")):
        suggested = cost / (Decimal("1") - (target_margin / HUND))

    # 3) custom price overrides all
    if custom_price and custom_price > 0:
        suggested = custom_price

    # 4) discount
    if discount_percent > 0:
        suggested = suggested * (Decimal("1") - (discount_percent / HUND))

    # 5) min price
    if min_price and suggested < min_price:
        suggested = min_price

    suggested_with_vat = suggested * (Decimal("1") + (vat_percent / HUND)) if vat_percent else suggested

    # Contribution
    opex_amount_percent = suggested * (opex_percent / HUND) if opex_percent > 0 else D0
    contribution = suggested - cost - opex_unit - opex_amount_percent

    # breakeven units
    breakeven_units = (fixed_cost_total / contribution) if (fixed_cost_total > 0 and contribution > 0) else D0

    # extra indicators
    gross_profit = suggested - cost
    gross_margin = pct(gross_profit, suggested) if suggested > 0 else None

    net_profit = gross_profit - opex_unit - opex_amount_percent
    net_margin = pct(net_profit, suggested) if suggested > 0 else None

    payload = {
        "ok": True,
        "period": {"id": period.id if period else None, "label": str(period) if period else ""},
        "product": {"id": p.id, "code": p.code, "name": p.name},

        "cost": float(money(cost)),
        "current_price": float(money(current_price)),

        "suggested_price": float(money(suggested)),
        "suggested_price_vat": float(money(suggested_with_vat)),

        "gross_profit": float(money(gross_profit)),
        "gross_margin_percent": float(money(gross_margin)) if gross_margin is not None else None,

        "opex_amount_percent": float(money(opex_amount_percent)),
        "opex_unit": float(money(opex_unit)),

        "net_profit": float(money(net_profit)),
        "net_margin_percent": float(money(net_margin)) if net_margin is not None else None,

        "contribution_per_unit": float(money(contribution)),
        "breakeven_units": float(money(breakeven_units)),

        "notes": "التكلفة من BOM.unit_cost_final إن وجدت، وإلا يتم حسابها حسب الفترة."
    }
    return JsonResponse(payload)


# =========================
# 3) Product P&L (needs hooks wiring)
# =========================
def get_sales_agg(period, product: Product):
    """
    لازم ترجع:
      prod_qty, prod_sales, total_qty, total_sales
    اربطها بموديلاتك (SalesInvoiceItem/SalesSummary...) لاحقًا
    """
    return D0, D0, D0, D0


def get_expenses_by_group(period):
    """
    لازم ترجع dict: {group_name: amount}
    اربطها بموديلاتك لاحقًا (ExpenseLine/AccountGroup...)
    """
    return {}


def alloc_ratio(alloc_mode: str, w_sales, w_qty, prod_sales, total_sales, prod_qty, total_qty):
    alloc_mode = (alloc_mode or "sales").lower()

    sales_ratio = (prod_sales / total_sales) if total_sales > 0 else D0
    qty_ratio = (prod_qty / total_qty) if total_qty > 0 else D0

    if alloc_mode == "qty":
        return qty_ratio

    if alloc_mode == "hybrid":
        w_sales = d(w_sales)
        w_qty = d(w_qty)
        s = w_sales + w_qty
        if s <= 0:
            return sales_ratio
        return (sales_ratio * (w_sales / s)) + (qty_ratio * (w_qty / s))

    return sales_ratio


@staff_member_required
@require_GET
def pricing_product_pnl(request):
    product_id = request.GET.get("product")
    if not product_id:
        return JsonResponse({"ok": False, "error": "product is required"}, status=400)

    product = Product.objects.filter(id=product_id).first()
    if not product:
        return JsonResponse({"ok": False, "error": "product not found"}, status=404)

    period = get_period(request.GET.get("period"))
    if not period:
        return JsonResponse({"ok": False, "error": "no period found"}, status=400)

    alloc_mode = request.GET.get("alloc_mode", "sales")
    w_sales = request.GET.get("w_sales", "50")
    w_qty = request.GET.get("w_qty", "50")

    # sales agg
    prod_qty, prod_sales, total_qty, total_sales = get_sales_agg(period, product)
    prod_qty, prod_sales, total_qty, total_sales = d(prod_qty), d(prod_sales), d(total_qty), d(total_sales)

    # cogs
    bom = product.get_active_bom()
    unit_cost = (getattr(bom, "unit_cost_final", None) if bom else None) or product.compute_unit_cost(period=period)
    unit_cost = d(unit_cost)
    cogs = unit_cost * prod_qty

    # expenses by group
    exp_groups = get_expenses_by_group(period) or {}
    total_expenses = sum((d(v) for v in exp_groups.values()), D0)

    # allocation ratio
    ratio = alloc_ratio(alloc_mode, w_sales, w_qty, prod_sales, total_sales, prod_qty, total_qty)

    allocated_groups = []
    allocated_total = D0
    for g, amt in exp_groups.items():
        amt = d(amt)
        alloc_amt = amt * ratio
        allocated_total += alloc_amt
        allocated_groups.append({
            "group": str(g),
            "total_period": float(money(amt)),
            "allocated": float(money(alloc_amt)),
        })

    gross_profit = prod_sales - cogs
    net_profit = gross_profit - allocated_total

    payload = {
        "ok": True,
        "period": {"id": period.id, "label": str(period)},
        "product": {"id": product.id, "code": product.code, "name": product.name},
        "alloc": {
            "mode": alloc_mode,
            "w_sales": float(d(w_sales)),
            "w_qty": float(d(w_qty)),
            "ratio_percent": float(money(ratio * HUND)),
        },
        "sales": {
            "prod_qty": float(money(prod_qty)),
            "prod_sales": float(money(prod_sales)),
            "total_sales": float(money(total_sales)),
            "sales_share_percent": float(money((prod_sales / total_sales * HUND) if total_sales > 0 else 0)),
            "qty_share_percent": float(money((prod_qty / total_qty * HUND) if total_qty > 0 else 0)),
        },
        "cogs": {
            "unit_cost": float(money(unit_cost)),
            "cogs_total": float(money(cogs)),
            "cogs_percent_of_sales": float(money((cogs / prod_sales * HUND) if prod_sales > 0 else 0)),
        },
        "pnl": {
            "gross_profit": float(money(gross_profit)),
            "gross_margin_percent": float(money((gross_profit / prod_sales * HUND) if prod_sales > 0 else 0)),
            "allocated_opex_total": float(money(allocated_total)),
            "allocated_opex_percent_of_sales": float(money((allocated_total / prod_sales * HUND) if prod_sales > 0 else 0)),
            "net_profit": float(money(net_profit)),
            "net_margin_percent": float(money((net_profit / prod_sales * HUND) if prod_sales > 0 else 0)),
        },
        "expenses": {
            "total_expenses_period": float(money(total_expenses)),
            "groups": allocated_groups,
        },
        "notes": "لتفعيل P&L الحقيقي: اربط get_sales_agg و get_expenses_by_group بموديلات المبيعات/المصروفات."
    }
    return JsonResponse(payload, safe=False)


# =========================
# 4) Scenarios (placeholders)
# =========================
@staff_member_required
@require_http_methods(["POST"])
def pricing_save_scenario(request):
    return JsonResponse({"ok": False, "error": "pricing_save_scenario not implemented yet"}, status=501)


@staff_member_required
@require_http_methods(["GET"])
def pricing_load_scenario(request, scenario_id: int):
    return JsonResponse({"ok": False, "error": "pricing_load_scenario not implemented yet", "scenario_id": scenario_id}, status=501)
