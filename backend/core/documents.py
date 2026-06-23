import streamlit as st
import pandas as pd
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
import io
import qrcode
from PIL import Image as PILImage

# ==============================
# PDF GENERATION
# ==============================

def generate_proforma_invoice(data):
    """Generate Proforma Invoice PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a2e'),
        alignment=1
    )
    story.append(Paragraph("PROFORMA INVOICE", title_style))
    story.append(Spacer(1, 20))
    
    # Company Info
    company_style = ParagraphStyle(
        'Company',
        parent=styles['Normal'],
        fontSize=10,
        alignment=0
    )
    story.append(Paragraph("AZIEL INVESTMENTS", company_style))
    story.append(Paragraph("Retreat Park, Harare", company_style))
    story.append(Paragraph("Tel: +263 772 123 456", company_style))
    story.append(Spacer(1, 20))
    
    # Invoice Details
    detail_data = [
        ["Invoice No:", data.get('invoice_no', 'INV-001')],
        ["Date:", data.get('date', datetime.now().strftime('%Y-%m-%d'))],
        ["Customer:", data.get('customer', 'Walk-in Customer')],
        ["Valid Until:", data.get('valid_until', '30 days from date')]
    ]
    
    detail_table = Table(detail_data, colWidths=[2*inch, 4*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 20))
    
    # Items Table
    items_data = [["Item", "Quantity", "Unit Price", "Total"]]
    for item in data.get('items', []):
        items_data.append([
            item.get('name', ''),
            item.get('quantity', 1),
            f"${item.get('price', 0):.2f}",
            f"${item.get('total', 0):.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # Totals
    total_data = [
        ["Subtotal:", f"${data.get('subtotal', 0):.2f}"],
        ["Tax ({data.get('tax_rate', 0)}%):", f"${data.get('tax', 0):.2f}"],
        ["Total:", f"${data.get('total', 0):.2f}"]
    ]
    
    total_table = Table(total_data, colWidths=[4*inch, 2*inch])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story.append(total_table)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_delivery_note(data):
    """Generate Delivery Note PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, alignment=1)
    story.append(Paragraph("DELIVERY NOTE", title_style))
    story.append(Spacer(1, 20))
    
    # Delivery Details
    story.append(Paragraph(f"<b>Delivery Note No:</b> {data.get('note_no', 'DN-001')}", styles['Normal']))
    story.append(Paragraph(f"<b>Date:</b> {data.get('date', datetime.now().strftime('%Y-%m-%d'))}", styles['Normal']))
    story.append(Paragraph(f"<b>Customer:</b> {data.get('customer', 'Walk-in Customer')}", styles['Normal']))
    story.append(Paragraph(f"<b>Delivery Address:</b> {data.get('address', 'Store Pickup')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Items
    items_data = [["Item", "Quantity"]]
    for item in data.get('items', []):
        items_data.append([item.get('name', ''), item.get('quantity', 1)])
    
    items_table = Table(items_data, colWidths=[4*inch, 2*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 30))
    
    # Signature
    story.append(Paragraph("Received by: ____________________", styles['Normal']))
    story.append(Paragraph("Date: ____________________", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_credit_note(data):
    """Generate Credit Note PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.red, alignment=1)
    story.append(Paragraph("CREDIT NOTE", title_style))
    story.append(Spacer(1, 20))
    
    # Credit Details
    story.append(Paragraph(f"<b>Credit Note No:</b> {data.get('note_no', 'CN-001')}", styles['Normal']))
    story.append(Paragraph(f"<b>Original Invoice:</b> {data.get('invoice_no', 'INV-001')}", styles['Normal']))
    story.append(Paragraph(f"<b>Date:</b> {data.get('date', datetime.now().strftime('%Y-%m-%d'))}", styles['Normal']))
    story.append(Paragraph(f"<b>Customer:</b> {data.get('customer', 'Walk-in Customer')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Items Returned
    items_data = [["Item", "Quantity", "Refund Amount"]]
    for item in data.get('items', []):
        items_data.append([
            item.get('name', ''),
            item.get('quantity', 1),
            f"${item.get('refund', 0):.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # Total
    story.append(Paragraph(f"<b>Total Credit Amount:</b> ${data.get('total', 0):.2f}", styles['Normal']))
    story.append(Paragraph("<b>Reason for Credit:</b> " + data.get('reason', 'Product Return'), styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_customer_statement(data):
    """Generate Customer Statement PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=20, alignment=1)
    story.append(Paragraph("CUSTOMER STATEMENT", title_style))
    story.append(Spacer(1, 20))
    
    # Customer Info
    story.append(Paragraph(f"<b>Customer:</b> {data.get('customer', '')}", styles['Normal']))
    story.append(Paragraph(f"<b>Phone:</b> {data.get('phone', '')}", styles['Normal']))
    story.append(Paragraph(f"<b>Statement Period:</b> {data.get('period', '')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Transactions
    trans_data = [["Date", "Invoice No", "Description", "Debit", "Credit", "Balance"]]
    for trans in data.get('transactions', []):
        trans_data.append([
            trans.get('date', ''),
            trans.get('invoice', ''),
            trans.get('description', ''),
            f"${trans.get('debit', 0):.2f}" if trans.get('debit', 0) > 0 else "-",
            f"${trans.get('credit', 0):.2f}" if trans.get('credit', 0) > 0 else "-",
            f"${trans.get('balance', 0):.2f}"
        ])
    
    trans_table = Table(trans_data, colWidths=[1.2*inch, 1.2*inch, 1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    trans_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    story.append(trans_table)
    story.append(Spacer(1, 20))
    
    # Summary
    story.append(Paragraph(f"<b>Opening Balance:</b> ${data.get('opening_balance', 0):.2f}", styles['Normal']))
    story.append(Paragraph(f"<b>Total Debits:</b> ${data.get('total_debits', 0):.2f}", styles['Normal']))
    story.append(Paragraph(f"<b>Total Credits:</b> ${data.get('total_credits', 0):.2f}", styles['Normal']))
    story.append(Paragraph(f"<b>Closing Balance:</b> ${data.get('closing_balance', 0):.2f}", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_purchase_order(data):
    """Generate Purchase Order PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, alignment=1)
    story.append(Paragraph("PURCHASE ORDER", title_style))
    story.append(Spacer(1, 20))
    
    # PO Details
    story.append(Paragraph(f"<b>PO Number:</b> {data.get('po_number', 'PO-001')}", styles['Normal']))
    story.append(Paragraph(f"<b>Date:</b> {data.get('date', datetime.now().strftime('%Y-%m-%d'))}", styles['Normal']))
    story.append(Paragraph(f"<b>Supplier:</b> {data.get('supplier', '')}", styles['Normal']))
    story.append(Paragraph(f"<b>Delivery Date:</b> {data.get('delivery_date', 'TBD')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Items
    items_data = [["Item", "Quantity", "Unit Cost", "Total"]]
    for item in data.get('items', []):
        items_data.append([
            item.get('name', ''),
            item.get('quantity', 1),
            f"${item.get('cost', 0):.2f}",
            f"${item.get('total', 0):.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # Total
    story.append(Paragraph(f"<b>Total Amount:</b> ${data.get('total', 0):.2f}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Terms
    story.append(Paragraph("<b>Terms & Conditions:</b>", styles['Normal']))
    story.append(Paragraph(data.get('terms', 'Standard payment terms apply'), styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================
# PDF DOWNLOAD BUTTONS
# ==============================

def download_pdf_button(pdf_buffer, filename, button_text="📄 Download PDF"):
    """Create download button for PDF"""
    st.download_button(
        label=button_text,
        data=pdf_buffer,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True
    )

# ==============================
# QR CODE GENERATION
# ==============================

def generate_qr_code(data):
    """Generate QR code for product or customer"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer