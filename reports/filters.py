from django import template
register = template.Library()

@register.filter
def sum(queryset, field):
    total = 0
    for item in queryset:
        value = getattr(item, field, 0)
        if value:
            total += value
    return total
