# expenses/admin.py
from decimal import Decimal

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils.html import format_html

from .models import (
    Period,
    ExpenseCategory, ExpenseItem,
    ExpenseBatch, ExpenseLine,
)

# =========================
# Helpers
# =========================

def _sum_lines(batch: ExpenseBatch, nature: str | None = None):
    qs = ExpenseLine.objects.filter(batch=batch)
    if nature:
        qs = qs.filter(item__category__nature=nature)
    return qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


def ensure_lines_for_batch(batch: ExpenseBatch):
    """
    ✅ ضمان وجود ExpenseLine لكل ExpenseItem (النشط فقط) داخل هذا الـ batch
    """
    # فقط النشطة
    items_qs = ExpenseItem.objects.filter(is_active=True).only("id")

    existing = set(
        ExpenseLine.objects.filter(batch=batch).values_list("item_id", flat=True)
    )

    to_create = []
    for it in items_qs:
        if it.id not in existing:
            to_create.append(
                ExpenseLine(batch=batch, item_id=it.id, amount=Decimal("0.00"), notes="")
            )

    if to_create:
        ExpenseLine.objects.bulk_create(to_create)


# =========================
# Inlines حسب Nature
# =========================

class BaseExpenseLineInline(admin.TabularInline):
    model = ExpenseLine
    extra = 0
    can_delete = False
    fields = ("item", "amount", "notes")
    readonly_fields = ("item",)

    nature_code = None  # override

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("item", "item__category")
        if self.nature_code:
            qs = qs.filter(item__category__nature=self.nature_code)
        return qs

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        # ✅ لو الفترة مقفلة امنع التعديل داخل السطور
        if obj and obj.period and obj.period.is_closed:
            return request.method not in ("POST",)
        return super().has_change_permission(request, obj=obj)


class ExpenseLineInlineOP(BaseExpenseLineInline):
    verbose_name = "تشغيلي"
    verbose_name_plural = "تشغيلي (OP)"
    nature_code = "OP"


class ExpenseLineInlineSA(BaseExpenseLineInline):
    verbose_name = "بيعي"
    verbose_name_plural = "بيعي (SA)"
    nature_code = "SA"


class ExpenseLineInlineAD(BaseExpenseLineInline):
    verbose_name = "إداري"
    verbose_name_plural = "إداري (AD)"
    nature_code = "AD"


# =========================
# Admin
# =========================

@admin.register(ExpenseBatch)
class ExpenseBatchAdmin(admin.ModelAdmin):
    list_display = ("period", "totals_badge")
    list_filter = ("period__year", "period__month")
    inlines = [ExpenseLineInlineOP, ExpenseLineInlineSA, ExpenseLineInlineAD]

    change_form_template = "admin/expenses/expensebatch/change_form.html"

    def totals_badge(self, obj):
        op = _sum_lines(obj, "OP")
        sa = _sum_lines(obj, "SA")
        ad = _sum_lines(obj, "AD")
        total = op + sa + ad
        return format_html(
            "<span style='white-space:nowrap'>"
            "<b>OP:</b> {} | <b>SA:</b> {} | <b>AD:</b> {} | <b>ALL:</b> {}"
            "</span>",
            op, sa, ad, total
        )
    totals_badge.short_description = "إجماليات"

    def has_change_permission(self, request, obj=None):
        # ✅ لو الفترة مقفلة: عرض فقط، منع POST
        if obj and obj.period and obj.period.is_closed and request.method == "POST":
            return False
        return super().has_change_permission(request, obj=obj)

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.period and obj.period.is_closed:
            ro += [f.name for f in self.model._meta.fields]
        return ro

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        # ✅ عند فتح صفحة التعديل: أنشئ السطور أولاً (GET فقط)
        if object_id and request.method == "GET":
            obj = ExpenseBatch.objects.filter(pk=object_id).select_related("period").first()
            if obj:
                ensure_lines_for_batch(obj)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        # ✅ منع الحفظ لو الفترة مقفلة (احتياط)
        if obj.period and obj.period.is_closed:
            raise ValidationError("هذه الفترة مقفلة، لا يمكن الحفظ.")
        super().save_model(request, obj, form, change)
        ensure_lines_for_batch(obj)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            op = _sum_lines(obj, "OP")
            sa = _sum_lines(obj, "SA")
            ad = _sum_lines(obj, "AD")
            total = op + sa + ad
            extra_context.update({
                "total_op": op,
                "total_sa": sa,
                "total_ad": ad,
                "total_all": total,
                "section_totals": {"OP": op, "SA": sa, "AD": ad}
            })
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "nature", "directness", "frequency", "behavior", "is_active")
    list_filter = ("nature", "directness", "frequency", "behavior", "is_active")
    search_fields = ("code", "name")
    ordering = ("code",)
    list_editable = ("is_active",)


@admin.register(ExpenseItem)
class ExpenseItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "default_amount", "is_active")
    list_filter = ("category__nature", "is_active")
    search_fields = ("code", "name", "category__code", "category__name")
    ordering = ("code",)
    list_editable = ("default_amount", "is_active")
    autocomplete_fields = ("category",)
