from django import forms
from expenses.models import Period


class StockCountImportForm(forms.Form):
    period = forms.ModelChoiceField(
        queryset=Period.objects.all(),
        label="الفترة",
    )
    count_type = forms.ChoiceField(
        label="نوع الجرد",
        choices=[("OPENING", "جرد أول الفترة"), ("CLOSING", "جرد آخر الفترة")],
    )
    count_date = forms.DateField(label="تاريخ الجرد")
    excel_file = forms.FileField(label="ملف إكسل للجرد")
