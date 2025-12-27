from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from expenses.models import Period



from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def pricing_dashboard(request):
    embed = request.GET.get("embed") == "1"
    return render(request, "pricing/dashboard.html", {"embed": embed})



@staff_member_required
def pricing_dashboard(request):
    embed = request.GET.get("embed") == "1"
    periods = Period.objects.order_by("year", "month")
    period_id = request.GET.get("period")
    period = Period.objects.filter(id=period_id).first() if period_id else periods.first()

    return render(request, "pricing/dashboard.html", {
        "embed": embed,
        "periods": periods,
        "period": period,
    })


from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from expenses.models import Period
from costing.models import Product

@staff_member_required
def pricing_product(request):
    embed = request.GET.get("embed") == "1"

    periods = Period.objects.order_by("year", "month")
    period_id = request.GET.get("period")
    period = Period.objects.filter(id=period_id).first() if period_id else periods.last()

    products = Product.objects.filter(is_sellable=True, is_semi_finished=False).order_by("code")

    # اختيار منتج افتراضي
    product_id = request.GET.get("product")
    product = Product.objects.filter(id=product_id).first() if product_id else products.first()

    return render(request, "pricing/product.html", {
        "embed": embed,
        "periods": periods,
        "period": period,
        "products": products,
        "product": product,
    })
