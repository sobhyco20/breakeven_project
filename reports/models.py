# reports/models.py
from django.db import models


class InventoryReports(models.Model):
    """
    موديل بسيط جداً الهدف منه فقط ظهور موديول 'التقارير'
    داخل لوحة التحكم، مع صفحة روابط للتقارير.
    لا نحتاج أي حقول حقيقية هنا.
    """

    class Meta:
        verbose_name = "التقارير"
        verbose_name_plural = "التقارير"

    def __str__(self):
        return "التقارير"
