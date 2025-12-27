# pricing/services/run_pricing.py
from decimal import Decimal

from pricing.services.pricing_engine import calculate_price
from pricing.models import PricingResult,PricingContext


def run_pricing(policy):
    """
    policy = PricingPolicy
    يحسب تكلفة الوحدة من BOM عبر Product.compute_unit_cost(period)
    ثم يحسب سعر البيع ويخزن النتيجة
    """
    context = PricingContext.objects.get(
        product=policy.product,
        period=policy.period
    )

    cost_per_unit = context.full_cost

    result = calculate_price(cost_per_unit, policy)

    PricingResult.objects.update_or_create(
        pricing_policy=policy,
        defaults={"cost_per_unit": cost_per_unit, **result},
    )
    return cost_per_unit, result
