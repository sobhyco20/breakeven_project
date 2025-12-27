# purchases/forms.py
from django import forms
from expenses.models import Period


class PurchaseSummaryImportForm(forms.Form):
    period = forms.ModelChoiceField(
        queryset=Period.objects.all(),
        label="الفترة"
    )
    excel_file = forms.FileField(label="ملف إكسل للمشتريات")
