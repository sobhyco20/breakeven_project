# purchases/views.py
from collections import defaultdict
from decimal import Decimal

from django.shortcuts import render
from purchases.models import PurchaseSummary, PurchaseSummaryLine
from expenses.models import Period
from io import BytesIO
from django.http import HttpResponse

# Excel
from openpyxl import Workbook

# PDF
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet



def purchase_price_comparison_view(request):
    # استلام الفترات المختارة من الـ GET (قائمة IDs)
    selected_period_ids_raw = request.GET.getlist("periods")
    selected_period_ids = []
    for v in selected_period_ids_raw:
        try:
            selected_period_ids.append(int(v))
        except ValueError:
            pass

    # جميع الفترات (لإظهارها في الفلاتر)
    all_periods = Period.objects.all().order_by("id")

    # لو تم اختيار فترات
    selected_periods = all_periods.filter(id__in=selected_period_ids) if selected_period_ids else []

    result_rows = []
    if selected_periods:
        # نجلب ملخصات المشتريات لهذه الفترات
        summaries = PurchaseSummary.objects.filter(period__in=selected_periods)

        # نجلب تفاصيل المشتريات
        lines = (
            PurchaseSummaryLine.objects
            .filter(summary__in=summaries)
            .select_related("raw_material", "summary__period")
            .order_by("raw_material__name", "summary__period__id")
        )

        # تجميع البيانات: لكل مادة -> لكل فترة -> سعر الوحدة
        data = defaultdict(dict)  # {raw_material: {period: unit_cost}}

        for line in lines:
            rm = line.raw_material
            period = line.summary.period
            data[rm][period] = line.unit_cost

        # تجهيز صفوف النتيجة مع الإحصائيات
        for rm, period_prices in data.items():
            row = {
                "raw_material": rm,
                "prices": [],  # ستكون قائمة بنفس ترتيب selected_periods
                "max_price": None,
                "min_price": None,
                "avg_price": None,
                "change_percent": None,
            }

            numeric_prices = []
            ordered_prices = []

            # نجمع الأسعار بالترتيب (قد تحتوي على None)
            for period in selected_periods:
                price = period_prices.get(period)
                ordered_prices.append(price)
                if price is not None:
                    numeric_prices.append(Decimal(price))

            # حساب الإحصائيات كالعادة
            if numeric_prices:
                max_p = max(numeric_prices)
                min_p = min(numeric_prices)
                avg_p = sum(numeric_prices) / Decimal(len(numeric_prices))

                row["max_price"] = max_p
                row["min_price"] = min_p
                row["avg_price"] = avg_p

                if len(numeric_prices) >= 2 and numeric_prices[0] != 0:
                    change = ((numeric_prices[-1] - numeric_prices[0]) / numeric_prices[0]) * Decimal("100")
                    row["change_percent"] = change

            # 🔴 تحديد الخلايا التي حصل فيها تباين في السعر
            # لو كل الأسعار متساوية -> لا تلوين
            non_null = [p for p in ordered_prices if p is not None]
            distinct_non_null = set(non_null)

            if len(distinct_non_null) > 1:
                # في حالة وجود تباين، نعتبر أن الأساس هو أول سعر غير فارغ
                base_price = non_null[0]
            else:
                base_price = None

            # إعادة بناء قائمة prices مع فلاغ changed
            row["prices"] = []
            for period, price in zip(selected_periods, ordered_prices):
                changed = False
                if base_price is not None and price is not None and price != base_price:
                    changed = True

                row["prices"].append({
                    "period": period,
                    "price": price,
                    "changed": changed,
                })

            result_rows.append(row)

    export = request.GET.get("export")
    if export in ("excel", "pdf") and selected_periods and result_rows:
        if export == "excel":
            return export_purchase_price_comparison_excel(selected_periods, result_rows)
        else:
            return export_purchase_price_comparison_pdf(selected_periods, result_rows)

    context = {
        "all_periods": all_periods,
        "selected_period_ids": selected_period_ids,
        "selected_periods": selected_periods,
        "rows": result_rows,
    }
    return render(request, "purchases/purchase_price_comparison.html", context)


from io import BytesIO
from django.http import HttpResponse
from openpyxl import Workbook


def export_purchase_price_comparison_excel(selected_periods, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "مقارنة أسعار المشتريات"

    # ---------------- الهيدر ----------------
    header = ["كود المادة", "اسم المادة"] + [p.name for p in selected_periods] + [
        "أعلى سعر", "أقل سعر", "متوسط السعر", "نسبة التغير (%)"
    ]
    ws.append(header)

    # ---------------- البيانات ----------------
    for row in rows:
        line = [
            getattr(row["raw_material"], "sku", ""),
            row["raw_material"].name,
        ]

        # أسعار الفترات
        for item in row["prices"]:
            if item["price"] is not None:
                line.append(float(item["price"]))
            else:
                line.append("")

        # دالة مساعدة لتحويل الـ Decimal لرقم عادي أو فراغ
        def _to_float(val):
            return float(val) if val is not None else ""

        # الإحصائيات
        line.append(_to_float(row["max_price"]))
        line.append(_to_float(row["min_price"]))
        line.append(_to_float(row["avg_price"]))
        line.append(float(row["change_percent"]) if row["change_percent"] is not None else "")

        # 🔴 مهم: هذه داخل الـ for
        ws.append(line)

    # ---------------- تجهيز الاستجابة ----------------
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="purchase_price_comparison.xlsx"'

    # 🔴 مهم: الحفظ والـ return خارج الـ for
    wb.save(response)
    return response



def export_purchase_price_comparison_pdf(selected_periods, rows):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)

    styles = getSampleStyleSheet()
    elements = []

    title = Paragraph("تقرير مقارنة أسعار المشتريات للمواد", styles["Title"])
    elements.append(title)

    # بيانات الجدول
    table_data = []
    header = ["كود المادة", "اسم المادة"] + [p.name for p in selected_periods] + [
        "أعلى سعر", "أقل سعر", "متوسط", "تغير (%)"
    ]
    table_data.append(header)

    for row in rows:
        line = [
            getattr(row["raw_material"], "code", ""),
            row["raw_material"].name,
        ]
        for item in row["prices"]:
            line.append(str(item["price"]) if item["price"] is not None else "")

        def _val(v):
            return f"{v:.3f}" if v is not None else ""

        line.append(_val(row["max_price"]))
        line.append(_val(row["min_price"]))
        line.append(_val(row["avg_price"]))
        line.append(f"{row['change_percent']:.2f}%" if row["change_percent"] is not None else "")

        table_data.append(line)

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ]))

    elements.append(table)
    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="purchase_price_comparison.pdf"'
    response.write(pdf)
    return response
