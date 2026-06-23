from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO


def generate_pl_pdf(report, year, month):

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()
    content = []

    title = f"Trading & Profit/Loss Account - {year}"
    if month:
        title += f" Month {month}"

    content.append(Paragraph(title, styles["Title"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph(f"Sales: {report['sales']}", styles["Normal"]))
    content.append(Paragraph(f"Purchases: {report['purchases']}", styles["Normal"]))
    content.append(Paragraph(f"Gross Profit: {report['gross_profit']}", styles["Normal"]))

    content.append(Spacer(1, 12))

    content.append(Paragraph(f"Income: {report['total_income']}", styles["Normal"]))
    content.append(Paragraph(f"Expenses: {report['total_expenses']}", styles["Normal"]))
    content.append(Paragraph(f"Net Profit: {report['net_profit']}", styles["Normal"]))

    doc.build(content)

    buffer.seek(0)
    return buffer