from django import forms


class RawMaterialImportForm(forms.Form):
    excel_file = forms.FileField(label="ملف إكسل للمواد الخام")



class ProductImportForm(forms.Form):
    excel_file = forms.FileField(label="ملف إكسل للمنتجات")

from django import forms

class BOMImportForm(forms.Form):
    excel_file = forms.FileField(label="ملف إكسل مكونات المنتجات")
