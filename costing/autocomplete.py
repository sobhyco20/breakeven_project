from dal import autocomplete
from .models import RawMaterial, Product


from dal import autocomplete
from .models import RawMaterial, Product


class MaterialAutocomplete(autocomplete.Select2ListView):
    """Autocomplete موحّد للمواد الخام والمنتجات."""

    def get_list(self):
        term = (self.q or "").strip()

        results = []

        # إذا كان term على شكل raw:PK أو prod:PK (قيمة محفوظة مسبقاً)
        if term.startswith("raw:") or term.startswith("prod:"):
            try:
                kind, pk = term.split(":", 1)
            except ValueError:
                kind, pk = None, None

            if kind == "raw":
                rm = RawMaterial.objects.filter(pk=pk).first()
                if rm:
                    return [(f"raw:{rm.pk}", f"مادة خام - {rm.name}")]
            elif kind == "prod":
                p = Product.objects.filter(pk=pk).first()
                if p:
                    return [(f"prod:{p.pk}", f"منتج - {p.name}")]

            return []

        # البحث العادي بالاسم
        raw_qs = RawMaterial.objects.all()
        prod_qs = Product.objects.all()

        if term:
            raw_qs = raw_qs.filter(name__icontains=term)
            prod_qs = prod_qs.filter(name__icontains=term)

        for rm in raw_qs.order_by("name")[:50]:
            results.append((f"raw:{rm.pk}", f"مادة خام - {rm.name}"))

        for p in prod_qs.order_by("name")[:50]:
            results.append((f"prod:{p.pk}", f"منتج - {p.name}"))

        return results
