# backend/analytics/pl_pdf.py

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime


def generate_pl_pdf(pl_data, year=None, month=None, quarter=None):
    """
    Generate a comprehensive Profit & Loss report PDF
    
    Args:
        pl_data: Dictionary from profit_loss_account()
        year: Year for the report
        month: Month for the report
        quarter: Quarter for the report
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(8.5 * inch, 11 * inch),
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=12,
        spaceAfter=6
    )
    
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=4
    )
    
    right_style = ParagraphStyle(
        'RightStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        spaceAfter=4
    )
    
    content = []
    
    # ==============================
    # HEADER
    # ==============================
    # Company name
    content.append(Paragraph("AZIEL INVESTMENTS", title_style))
    
    # Report title
    title = "Trading & Profit & Loss Account"
    if year:
        title += f" - {year}"
        if month:
            title += f" Month {month:02d}"
        elif quarter:
            title += f" Q{quarter}"
    
    content.append(Paragraph(title, ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=12
    )))
    
    # Date generated
    content.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M')}",
        ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    ))
    content.append(Spacer(1, 12))
    
    # ==============================
    # TRADING ACCOUNT
    # ==============================
    content.append(Paragraph("TRADING ACCOUNT", heading_style))
    content.append(Spacer(1, 6))
    
    # Trading account table
    trading_data = [
        ['Description', 'Amount ($)'],
        ['Sales', f"{pl_data.get('sales', 0):,.2f}"],
        ['Less: Sales Returns', f"({pl_data.get('sales_returns', 0):,.2f})"],
        ['Net Sales', f"{pl_data.get('net_sales', 0):,.2f}"],
        ['', ''],
        ['Opening Stock', f"{pl_data.get('opening_stock', 0):,.2f}"],
        ['Add: Purchases', f"{pl_data.get('purchases', 0):,.2f}"],
        ['Less: Purchase Returns', f"({pl_data.get('purchase_returns', 0):,.2f})"],
        ['Net Purchases', f"{pl_data.get('net_purchases', 0):,.2f}"],
        ['Goods Available for Sale', f"{pl_data.get('opening_stock', 0) + pl_data.get('net_purchases', 0):,.2f}"],
        ['Less: Closing Stock', f"({pl_data.get('closing_stock', 0):,.2f})"],
        ['Cost of Goods Sold', f"{pl_data.get('cogs', 0):,.2f}"],
        ['', ''],
        ['Gross Profit', f"{pl_data.get('gross_profit', 0):,.2f}"],
    ]
    
    trading_table = Table(trading_data, colWidths=[4*inch, 2*inch])
    trading_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    
    content.append(trading_table)
    content.append(Spacer(1, 6))
    
    # Gross profit margin
    gross_margin = pl_data.get('gross_margin', 0)
    content.append(Paragraph(
        f"Gross Profit Margin: <b>{gross_margin:.1f}%</b>",
        ParagraphStyle('MarginStyle', parent=styles['Normal'], fontSize=10, spaceAfter=12)
    ))
    
    content.append(Spacer(1, 12))
    
    # ==============================
    # PROFIT & LOSS ACCOUNT
    # ==============================
    content.append(Paragraph("PROFIT & LOSS ACCOUNT", heading_style))
    content.append(Spacer(1, 6))
    
    # P&L table
    pl_table_data = [
        ['Description', 'Amount ($)'],
        ['Gross Profit b/d', f"{pl_data.get('gross_profit', 0):,.2f}"],
        ['Add: Other Income', f"{pl_data.get('other_income', 0):,.2f}"],
        ['', ''],
        ['Less: Operating Expenses', f"({pl_data.get('operating_expenses', 0):,.2f})"],
        ['Less: Other Expenses', f"({pl_data.get('other_expenses', 0):,.2f})"],
        ['', ''],
        ['Net Profit Before Tax', f"{pl_data.get('net_profit_before_tax', 0):,.2f}"],
        ['Less: Tax', f"({pl_data.get('tax', 0):,.2f})"],
        ['', ''],
        ['Net Profit After Tax', f"{pl_data.get('net_profit', 0):,.2f}"],
    ]
    
    pl_table = Table(pl_table_data, colWidths=[4*inch, 2*inch])
    pl_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    
    content.append(pl_table)
    content.append(Spacer(1, 6))
    
    # Net profit margin
    net_margin = pl_data.get('net_margin', 0)
    content.append(Paragraph(
        f"Net Profit Margin: <b>{net_margin:.1f}%</b>",
        ParagraphStyle('MarginStyle', parent=styles['Normal'], fontSize=10, spaceAfter=12)
    ))
    
    content.append(Spacer(1, 12))
    
    # ==============================
    # KEY METRICS SUMMARY
    # ==============================
    content.append(PageBreak())
    content.append(Paragraph("KEY PERFORMANCE METRICS", heading_style))
    content.append(Spacer(1, 6))
    
    metrics_data = [
        ['Metric', 'Value'],
        ['Total Sales', f"${pl_data.get('net_sales', 0):,.2f}"],
        ['Gross Profit', f"${pl_data.get('gross_profit', 0):,.2f}"],
        ['Gross Margin', f"{pl_data.get('gross_margin', 0):.1f}%"],
        ['Operating Expenses', f"${pl_data.get('operating_expenses', 0):,.2f}"],
        ['Net Profit', f"${pl_data.get('net_profit', 0):,.2f}"],
        ['Net Margin', f"{pl_data.get('net_margin', 0):.1f}%"],
        ['Transactions', f"{pl_data.get('transactions', 0):,}"],
        ['Items Sold', f"{pl_data.get('items_sold', 0):,.0f}"],
        ['Average Transaction', f"${pl_data.get('avg_transaction', 0):,.2f}"],
    ]
    
    metrics_table = Table(metrics_data, colWidths=[3*inch, 3*inch])
    metrics_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    
    content.append(metrics_table)
    content.append(Spacer(1, 12))
    
    # ==============================
    # PROFITABILITY STATUS
    # ==============================
    content.append(Paragraph("PROFITABILITY STATUS", heading_style))
    content.append(Spacer(1, 6))
    
    net_profit = pl_data.get('net_profit', 0)
    gross_margin = pl_data.get('gross_margin', 0)
    
    if net_profit > 0 and gross_margin > 30:
        status = "✅ EXCELLENT - Strong profitability"
        status_color = colors.green
    elif net_profit > 0 and gross_margin > 15:
        status = "✅ GOOD - Healthy profitability"
        status_color = colors.green
    elif net_profit > 0:
        status = "⚠️ FAIR - Needs improvement"
        status_color = colors.orange
    else:
        status = "❌ CRITICAL - Operating at a loss"
        status_color = colors.red
    
    status_style = ParagraphStyle(
        'StatusStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=status_color,
        spaceAfter=6
    )
    content.append(Paragraph(status, status_style))
    
    # Additional insights
    content.append(Spacer(1, 6))
    insights = []
    
    if gross_margin > 40:
        insights.append("• Excellent gross margin - pricing strategy is effective")
    elif gross_margin > 25:
        insights.append("• Healthy gross margin - good product mix")
    else:
        insights.append("• Low gross margin - consider reviewing pricing or supplier costs")
    
    if pl_data.get('transactions', 0) > 0:
        avg_trans = pl_data.get('avg_transaction', 0)
        if avg_trans > 50:
            insights.append(f"• Strong average transaction value of ${avg_trans:.2f}")
        elif avg_trans > 20:
            insights.append(f"• Moderate average transaction value of ${avg_trans:.2f}")
        else:
            insights.append(f"• Low average transaction value of ${avg_trans:.2f} - consider upselling")
    
    for insight in insights:
        content.append(Paragraph(insight, normal_style))
    
    content.append(Spacer(1, 12))
    
    # ==============================
    # FOOTER
    # ==============================
    content.append(Spacer(1, 24))
    content.append(Paragraph(
        "This report is generated automatically by AZIEL INVESTMENTS POS System",
        ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    ))
    content.append(Paragraph(
        f"Page 1/1",
        ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    ))
    
    # ==============================
    # BUILD PDF
    # ==============================
    doc.build(content)
    
    buffer.seek(0)
    return buffer


def generate_profit_center_pdf(analysis_data, start_date=None, end_date=None):
    """
    Generate a Profit Center Analysis PDF report
    
    Args:
        analysis_data: Dictionary from profit_center_analysis
        start_date: Start date for the report
        end_date: End date for the report
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(8.5 * inch, 11 * inch),
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    styles = getSampleStyleSheet()
    content = []
    
    # Header
    content.append(Paragraph("AZIEL INVESTMENTS", ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12
    )))
    
    content.append(Paragraph("PROFIT CENTER ANALYSIS", ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=12
    )))
    
    if start_date and end_date:
        content.append(Paragraph(
            f"Period: {start_date} to {end_date}",
            ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER)
        ))
    
    content.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M')}",
        ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    ))
    content.append(Spacer(1, 12))
    
    # Key metrics
    content.append(Paragraph("KEY METRICS", heading_style))
    content.append(Spacer(1, 6))
    
    metrics_data = [
        ['Metric', 'Value'],
        ['Total Revenue', f"${analysis_data.get('total_revenue', 0):,.2f}"],
        ['Total Profit', f"${analysis_data.get('total_profit', 0):,.2f}"],
        ['Profit Margin', f"{analysis_data.get('profit_margin', 0):.1f}%"],
        ['Total Transactions', f"{analysis_data.get('total_transactions', 0):,}"],
        ['Average Transaction', f"${analysis_data.get('avg_transaction', 0):,.2f}"],
    ]
    
    metrics_table = Table(metrics_data, colWidths=[3*inch, 3*inch])
    metrics_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    
    content.append(metrics_table)
    content.append(Spacer(1, 12))
    
    # Top products
    if analysis_data.get('top_products'):
        content.append(Paragraph("TOP PRODUCTS BY REVENUE", heading_style))
        content.append(Spacer(1, 6))
        
        top_products_data = [['Product', 'Revenue', 'Quantity']]
        for product, data in analysis_data['top_products'].items():
            top_products_data.append([
                product[:30],  # Truncate long names
                f"${data.get('revenue', 0):,.2f}",
                f"{data.get('quantity', 0):,.0f}"
            ])
        
        top_table = Table(top_products_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        top_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        content.append(top_table)
    
    # Build PDF
    doc.build(content)
    
    buffer.seek(0)
    return buffer