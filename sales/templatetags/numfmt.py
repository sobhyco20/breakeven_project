from decimal import Decimal, ROUND_HALF_UP
from django import template

register = template.Library()

@register.filter
def num(value, places=3):
    if value is None or value == "":
        return ""
    try:
        places = int(places)
        q = Decimal("1." + ("0" * places))
        d = Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)
        return format(d, f".{places}f")  # نقطة دائمًا
    except Exception:
        return value
