# pricing/services/pricing_engine.py
from decimal import Decimal, ROUND_HALF_UP

D0 = Decimal("0")
QTY3 = Decimal("0.001")
MONEY = Decimal("0.01")

def q3(v):
    return Decimal(str(v or "0")).quantize(QTY3, rounding=ROUND_HALF_UP)

def money(v):
    return Decimal(str(v or "0")).quantize(MONEY, rounding=ROUND_HALF_UP)

def calculate_price(cost_per_unit, policy):
    cost = Decimal(str(cost_per_unit or "0"))

    if policy.pricing_method == "margin_percent":
        price = cost * (Decimal("1") + (policy.margin_percent or D0) / 100)
    elif policy.pricing_method == "margin_amount":
        price = cost + (policy.margin_amount or D0)
    elif policy.pricing_method == "manual_price":
        price = policy.manual_price or D0
    else:
        price = cost

    price = money(price)
    profit = money(price - cost)
    margin = (profit / price * 100) if price > 0 else D0

    return {
        "selling_price": price,
        "gross_profit": profit,
        "gross_margin_percent": money(margin),
    }
