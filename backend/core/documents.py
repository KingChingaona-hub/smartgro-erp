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
# CONSTANTS
# ==============================
COMPANY_NAME = "AZIEL INVESTMENTS"
COMPANY_ADDRESS = "Retreat Park, Harare"
COMPANY_PHONE = "+263 78 290 5853"
COMPANY_EMAIL = "info@azielinvestments.co.zw"


def get_company_header():
    """Return company header for documents"""
    return f"""
    <b>{COMPANY_NAME}</b><br/>
    {COMPANY_ADDRESS}<br/>
    Tel: {COMPANY_PHONE} | Email: {COMPANY_EMAIL}
    """


def add_company_header_to_pdf(story, styles):
    """Add company header to PDF story"""
    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Normal'],
        fontSize=12,
        alignment=1,
        textColor=colors.HexColor('#1a237e'),
        fontName='Helvetica-Bold',
        spaceAfter=4
    )
    company_sub_style = ParagraphStyle(
        'CompanySub',
        parent=styles['Normal'],
        fontSize=10,
        alignment=1,
        textColor=colors.HexColor('#555555'),
        spaceAfter=2
    )
    
    story.append(Paragraph(COMPANY_NAME, company_style))
    story.append(Paragraph(COMPANY_ADDRESS, company_sub_style))
    story.append(Paragraph(f"Tel: {COMPANY_PHONE} | Email: {COMPANY_EMAIL}", company_sub_style))
    story.append(Spacer(1, 10))


def add_company_footer_to_pdf(story, styles):
    """Add company footer to PDF story"""
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        alignment=1,
        textColor=colors.HexColor('#888888'),
        spaceBefore=6
    )
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"{COMPANY_NAME} - {COMPANY_ADDRESS}", footer_style))
    story.append(Paragraph(f"Tel: {COMPANY_PHONE} | This is a computer-generated document", footer_style))
    story.append(Paragraph(f"© {datetime.now().year} {COMPANY_NAME}. All Rights Reserved.", footer_style))


# ==============================
# PDF GENERATION - WITH COMPANY NAME
# ==============================

def generate_proforma_invoice(data):
    """Generate Proforma Invoice PDF with company name"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Company Header
    add_company_header_to_pdf(story, styles)
    story.append(Spacer(1, 10))
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a1a2e'),
        alignment=1,
        spaceAfter=12
    )
    story.append(Paragraph("PROFORMA INVOICE", title_style))
    story.append(Spacer(1, 10))
    
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
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 15))
    
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))
    
    # Totals
    total_data = [
        ["Subtotal:", f"${data.get('subtotal', 0):.2f}"],
        ["Tax ({data.get('tax_rate', 0)}%):", f"${data.get('tax', 0):.2f}"],
        ["Total:", f"${data.get('total', 0):.2f}"]
    ]
    
    total_table = Table(total_data, colWidths=[4.5*inch, 1.5*inch])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TEXTCOLOR', (2, 2), (1, 2), colors.HexColor('#1a237e')),
        ('FONTSIZE', (0, 2), (1, 2), 14),
    ]))
    story.append(total_table)
    
    # Terms
    story.append(Spacer(1, 20))
    terms_style = ParagraphStyle(
        'Terms',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666')
    )
    story.append(Paragraph("<b>Terms & Conditions:</b>", terms_style))
    story.append(Paragraph("Payment due within 30 days of invoice date.", terms_style))
    story.append(Paragraph("All prices are in USD and exclude shipping.", terms_style))
    
    # Footer
    add_company_footer_to_pdf(story, styles)
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_delivery_note(data):
    """Generate Delivery Note PDF with company name"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Company Header
    add_company_header_to_pdf(story, styles)
    story.append(Spacer(1, 10))
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=1,
        textColor=colors.HexColor('#1a1a2e')
    )
    story.append(Paragraph("DELIVERY NOTE", title_style))
    story.append(Spacer(1, 15))
    
    # Delivery Details
    detail_style = ParagraphStyle(
        'Detail',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=4
    )
    story.append(Paragraph(f"<b>Delivery Note No:</b> {data.get('note_no', 'DN-001')}", detail_style))
    story.append(Paragraph(f"<b>Date:</b> {data.get('date', datetime.now().strftime('%Y-%m-%d'))}", detail_style))
    story.append(Paragraph(f"<b>Customer:</b> {data.get('customer', 'Walk-in Customer')}", detail_style))
    story.append(Paragraph(f"<b>Delivery Address:</b> {data.get('address', 'Store Pickup')}", detail_style))
    story.append(Spacer(1, 15))
    
    # Items
    items_data = [["Item", "Quantity"]]
    for item in data.get('items', []):
        items_data.append([item.get('name', ''), item.get('quantity', 1)])
    
    items_table = Table(items_data, colWidths=[4.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 30))
    
    # Signature
    story.append(Paragraph("Received by: ____________________", styles['Normal']))
    story.append(Paragraph("Date: ____________________", styles['Normal']))
    story.append(Paragraph("Signature: ____________________", styles['Normal']))
    
    # Footer
    add_company_footer_to_pdf(story, styles)
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_credit_note(data):
    """Generate Credit Note PDF with company name"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Company Header
    add_company_header_to_pdf(story, styles)
    story.append(Spacer(1, 10))
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.red,
        alignment=1
    )
    story.append(Paragraph("CREDIT NOTE", title_style))
    story.append(Spacer(1, 10))
    
    # Credit Details
    detail_style = ParagraphStyle(
        'Detail',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=4
    )
    story.append(Paragraph(f"<b>Credit Note No:</b> {data.get('note_no', 'CN-001')}", detail_style))
    story.append(Paragraph(f"<b>Original Invoice:</b> {data.get('invoice_no', 'INV-001')}", detail_style))
    story.append(Paragraph(f"<b>Date:</b> {data.get('date', datetime.now().strftime('%Y-%m-%d'))}", detail_style))
    story.append(Paragraph(f"<b>Customer:</b> {data.get('customer', 'Walk-in Customer')}", detail_style))
    story.append(Spacer(1, 15))
    
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))
    
    # Total
    story.append(Paragraph(f"<b>Total Credit Amount:</b> ${data.get('total', 0):.2f}", styles['Normal']))
    story.append(Paragraph(f"<b>Reason for Credit:</b> {data.get('reason', 'Product Return')}", styles['Normal']))
    
    # Footer
    add_company_footer_to_pdf(story, styles)
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_customer_statement(data):
    """Generate Customer Statement PDF with company name"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Company Header
    add_company_header_to_pdf(story, styles)
    story.append(Spacer(1, 10))
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=1,
        textColor=colors.HexColor('#1a1a2e')
    )
    story.append(Paragraph("CUSTOMER STATEMENT", title_style))
    story.append(Spacer(1, 10))
    
    # Customer Info
    detail_style = ParagraphStyle(
        'Detail',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=4
    )
    story.append(Paragraph(f"<b>Customer:</b> {data.get('customer', '')}", detail_style))
    story.append(Paragraph(f"<b>Phone:</b> {data.get('phone', '')}", detail_style))
    story.append(Paragraph(f"<b>Statement Period:</b> {data.get('period', '')}", detail_style))
    story.append(Spacer(1, 15))
    
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(trans_table)
    story.append(Spacer(1, 15))
    
    # Summary
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=4
    )
    story.append(Paragraph(f"<b>Opening Balance:</b> ${data.get('opening_balance', 0):.2f}", summary_style))
    story.append(Paragraph(f"<b>Total Debits:</b> ${data.get('total_debits', 0):.2f}", summary_style))
    story.append(Paragraph(f"<b>Total Credits:</b> ${data.get('total_credits', 0):.2f}", summary_style))
    story.append(Paragraph(f"<b>Closing Balance:</b> ${data.get('closing_balance', 0):.2f}", summary_style))
    
    # Footer
    add_company_footer_to_pdf(story, styles)
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_purchase_order(data):
    """Generate Purchase Order PDF with company name"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Company Header
    add_company_header_to_pdf(story, styles)
    story.append(Spacer(1, 10))
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=1,
        textColor=colors.HexColor('#1a1a2e')
    )
    story.append(Paragraph("PURCHASE ORDER", title_style))
    story.append(Spacer(1, 10))
    
    # PO Details
    detail_style = ParagraphStyle(
        'Detail',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=4
    )
    story.append(Paragraph(f"<b>PO Number:</b> {data.get('po_number', 'PO-001')}", detail_style))
    story.append(Paragraph(f"<b>Date:</b> {data.get('date', datetime.now().strftime('%Y-%m-%d'))}", detail_style))
    story.append(Paragraph(f"<b>Supplier:</b> {data.get('supplier', '')}", detail_style))
    story.append(Paragraph(f"<b>Delivery Date:</b> {data.get('delivery_date', 'TBD')}", detail_style))
    story.append(Spacer(1, 15))
    
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 15))
    
    # Total
    story.append(Paragraph(f"<b>Total Amount:</b> ${data.get('total', 0):.2f}", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Terms
    story.append(Paragraph("<b>Terms & Conditions:</b>", styles['Normal']))
    story.append(Paragraph(data.get('terms', 'Standard payment terms apply'), styles['Normal']))
    
    # Footer
    add_company_footer_to_pdf(story, styles)
    
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


# ==============================
# DOCUMENT MANAGEMENT DASHBOARD
# ==============================

def documents_dashboard():
    """Main documents dashboard"""
    
    st.title("Document Management")
    st.caption("Generate professional business documents")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access document management.")
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Proforma Invoice",
        "Delivery Note",
        "Credit Note",
        "Customer Statement",
        "Purchase Order"
    ])
    
    # ==============================
    # TAB 1: PROFORMA INVOICE
    # ==============================
    with tab1:
        st.markdown("## Generate Proforma Invoice")
        st.caption("Create a professional proforma invoice with company branding")
        
        col1, col2 = st.columns(2)
        
        with col1:
            invoice_no = st.text_input("Invoice Number", value=f"INV-{datetime.now().strftime('%Y%m%d')}-001")
            customer = st.text_input("Customer Name", placeholder="Walk-in Customer")
            valid_until = st.date_input("Valid Until", value=datetime.now() + pd.Timedelta(days=30))
        
        with col2:
            date = st.date_input("Date", value=datetime.now())
            tax_rate = st.number_input("Tax Rate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
        
        st.markdown("### Items")
        
        # Item input
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            item_name = st.text_input("Item Name", key="pi_item_name")
        with col2:
            item_qty = st.number_input("Qty", min_value=1, value=1, key="pi_qty")
        with col3:
            item_price = st.number_input("Price ($)", min_value=0.0, value=0.0, step=0.5, key="pi_price")
        with col4:
            if st.button("Add", key="pi_add"):
                if item_name and item_price > 0:
                    if "pi_items" not in st.session_state:
                        st.session_state.pi_items = []
                    st.session_state.pi_items.append({
                        "name": item_name,
                        "quantity": item_qty,
                        "price": item_price,
                        "total": item_qty * item_price
                    })
                    st.rerun()
        
        # Display items
        if "pi_items" not in st.session_state:
            st.session_state.pi_items = []
        
        if st.session_state.pi_items:
            items_df = pd.DataFrame(st.session_state.pi_items)
            st.dataframe(items_df, use_container_width=True, hide_index=True)
            
            subtotal = items_df["total"].sum()
            tax = subtotal * (tax_rate / 100)
            total = subtotal + tax
            
            st.info(f"**Subtotal:** ${subtotal:.2f} | **Tax:** ${tax:.2f} | **Total:** ${total:.2f}")
            
            if st.button("Clear Items", key="pi_clear"):
                st.session_state.pi_items = []
                st.rerun()
            
            if st.button("Generate Proforma Invoice", type="primary", key="pi_generate"):
                data = {
                    "invoice_no": invoice_no,
                    "date": date.strftime("%Y-%m-%d"),
                    "customer": customer if customer else "Walk-in Customer",
                    "valid_until": valid_until.strftime("%Y-%m-%d"),
                    "items": st.session_state.pi_items,
                    "subtotal": subtotal,
                    "tax_rate": tax_rate,
                    "tax": tax,
                    "total": total
                }
                
                pdf_buffer = generate_proforma_invoice(data)
                download_pdf_button(
                    pdf_buffer,
                    f"proforma_invoice_{invoice_no}.pdf",
                    "Download Proforma Invoice"
                )
    
    # ==============================
    # TAB 2: DELIVERY NOTE
    # ==============================
    with tab2:
        st.markdown("## Generate Delivery Note")
        st.caption("Create a professional delivery note with company branding")
        
        col1, col2 = st.columns(2)
        
        with col1:
            note_no = st.text_input("Delivery Note Number", value=f"DN-{datetime.now().strftime('%Y%m%d')}-001")
            customer = st.text_input("Customer Name", placeholder="Walk-in Customer")
        
        with col2:
            date = st.date_input("Date", value=datetime.now())
            address = st.text_input("Delivery Address", placeholder="Store Pickup")
        
        st.markdown("### Items")
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            item_name = st.text_input("Item Name", key="dn_item_name")
        with col2:
            item_qty = st.number_input("Qty", min_value=1, value=1, key="dn_qty")
        with col3:
            if st.button("Add", key="dn_add"):
                if item_name:
                    if "dn_items" not in st.session_state:
                        st.session_state.dn_items = []
                    st.session_state.dn_items.append({
                        "name": item_name,
                        "quantity": item_qty
                    })
                    st.rerun()
        
        if "dn_items" not in st.session_state:
            st.session_state.dn_items = []
        
        if st.session_state.dn_items:
            items_df = pd.DataFrame(st.session_state.dn_items)
            st.dataframe(items_df, use_container_width=True, hide_index=True)
            
            if st.button("Clear Items", key="dn_clear"):
                st.session_state.dn_items = []
                st.rerun()
            
            if st.button("Generate Delivery Note", type="primary", key="dn_generate"):
                data = {
                    "note_no": note_no,
                    "date": date.strftime("%Y-%m-%d"),
                    "customer": customer if customer else "Walk-in Customer",
                    "address": address if address else "Store Pickup",
                    "items": st.session_state.dn_items
                }
                
                pdf_buffer = generate_delivery_note(data)
                download_pdf_button(
                    pdf_buffer,
                    f"delivery_note_{note_no}.pdf",
                    "Download Delivery Note"
                )
    
    # ==============================
    # TAB 3: CREDIT NOTE
    # ==============================
    with tab3:
        st.markdown("## Generate Credit Note")
        st.caption("Create a professional credit note with company branding")
        
        col1, col2 = st.columns(2)
        
        with col1:
            note_no = st.text_input("Credit Note Number", value=f"CN-{datetime.now().strftime('%Y%m%d')}-001")
            invoice_no = st.text_input("Original Invoice Number", placeholder="INV-001")
            customer = st.text_input("Customer Name", placeholder="Walk-in Customer")
        
        with col2:
            date = st.date_input("Date", value=datetime.now())
            reason = st.text_input("Reason", placeholder="Product Return")
        
        st.markdown("### Items Returned")
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            item_name = st.text_input("Item Name", key="cn_item_name")
        with col2:
            item_qty = st.number_input("Qty", min_value=1, value=1, key="cn_qty")
        with col3:
            refund = st.number_input("Refund ($)", min_value=0.0, value=0.0, step=0.5, key="cn_refund")
        
        if st.button("Add", key="cn_add"):
            if item_name and refund > 0:
                if "cn_items" not in st.session_state:
                    st.session_state.cn_items = []
                st.session_state.cn_items.append({
                    "name": item_name,
                    "quantity": item_qty,
                    "refund": refund
                })
                st.rerun()
        
        if "cn_items" not in st.session_state:
            st.session_state.cn_items = []
        
        if st.session_state.cn_items:
            items_df = pd.DataFrame(st.session_state.cn_items)
            st.dataframe(items_df, use_container_width=True, hide_index=True)
            
            total = items_df["refund"].sum()
            st.info(f"**Total Credit Amount:** ${total:.2f}")
            
            if st.button("Clear Items", key="cn_clear"):
                st.session_state.cn_items = []
                st.rerun()
            
            if st.button("Generate Credit Note", type="primary", key="cn_generate"):
                data = {
                    "note_no": note_no,
                    "invoice_no": invoice_no if invoice_no else "N/A",
                    "date": date.strftime("%Y-%m-%d"),
                    "customer": customer if customer else "Walk-in Customer",
                    "items": st.session_state.cn_items,
                    "total": total,
                    "reason": reason if reason else "Product Return"
                }
                
                pdf_buffer = generate_credit_note(data)
                download_pdf_button(
                    pdf_buffer,
                    f"credit_note_{note_no}.pdf",
                    "Download Credit Note"
                )
    
    # ==============================
    # TAB 4: CUSTOMER STATEMENT - FIXED
    # ==============================
    with tab4:
        st.markdown("## Generate Customer Statement")
        st.caption("Create a professional customer statement with company branding")
        
        col1, col2 = st.columns(2)
        
        with col1:
            customer = st.text_input("Customer Name")
            phone = st.text_input("Phone Number")
        
        with col2:
            opening_balance = st.number_input("Opening Balance ($)", min_value=0.0, value=0.0, step=10.0)
            period = st.text_input("Statement Period", value=datetime.now().strftime("%B %Y"))
        
        st.markdown("### Transactions")
        
        col1, col2, col3, col4 = st.columns([1.5, 1.5, 1.5, 1.5])
        with col1:
            trans_date = st.date_input("Date", value=datetime.now(), key="cs_date")
        with col2:
            trans_invoice = st.text_input("Invoice No", key="cs_invoice")
        with col3:
            trans_debit = st.number_input("Debit ($)", min_value=0.0, value=0.0, step=5.0, key="cs_debit")
        with col4:
            trans_credit = st.number_input("Credit ($)", min_value=0.0, value=0.0, step=5.0, key="cs_credit")
        
        if st.button("Add Transaction", key="cs_add"):
            if trans_invoice or trans_debit > 0 or trans_credit > 0:
                if "cs_transactions" not in st.session_state:
                    st.session_state.cs_transactions = []
                st.session_state.cs_transactions.append({
                    "date": trans_date.strftime("%Y-%m-%d"),
                    "invoice": trans_invoice if trans_invoice else "N/A",
                    "description": "Sale" if trans_debit > 0 else "Payment" if trans_credit > 0 else "Adjustment",
                    "debit": trans_debit,
                    "credit": trans_credit
                })
                st.rerun()
        
        if "cs_transactions" not in st.session_state:
            st.session_state.cs_transactions = []
        
        if st.session_state.cs_transactions:
            trans_df = pd.DataFrame(st.session_state.cs_transactions)
            
            # Calculate running balance - FIXED: separate lines
            balance = opening_balance
            running_balances = []
            for _, row in trans_df.iterrows():
                balance += row["debit"] - row["credit"]
                running_balances.append(balance)
            trans_df["balance"] = running_balances
            
            st.dataframe(trans_df, use_container_width=True, hide_index=True)
            
            total_debits = trans_df["debit"].sum()
            total_credits = trans_df["credit"].sum()
            closing_balance = opening_balance + total_debits - total_credits
            
            st.info(f"**Opening Balance:** ${opening_balance:.2f} | **Total Debits:** ${total_debits:.2f} | **Total Credits:** ${total_credits:.2f} | **Closing Balance:** ${closing_balance:.2f}")
            
            if st.button("Clear Transactions", key="cs_clear"):
                st.session_state.cs_transactions = []
                st.rerun()
            
            if st.button("Generate Statement", type="primary", key="cs_generate"):
                data = {
                    "customer": customer if customer else "Unknown Customer",
                    "phone": phone if phone else "N/A",
                    "period": period,
                    "opening_balance": opening_balance,
                    "transactions": trans_df.to_dict('records'),
                    "total_debits": total_debits,
                    "total_credits": total_credits,
                    "closing_balance": closing_balance
                }
                
                pdf_buffer = generate_customer_statement(data)
                download_pdf_button(
                    pdf_buffer,
                    f"customer_statement_{customer.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    "Download Customer Statement"
                )
    
    # ==============================
    # TAB 5: PURCHASE ORDER
    # ==============================
    with tab5:
        st.markdown("## Generate Purchase Order")
        st.caption("Create a professional purchase order with company branding")
        
        col1, col2 = st.columns(2)
        
        with col1:
            po_number = st.text_input("PO Number", value=f"PO-{datetime.now().strftime('%Y%m%d')}-001")
            supplier = st.text_input("Supplier Name")
        
        with col2:
            date = st.date_input("Date", value=datetime.now())
            delivery_date = st.date_input("Delivery Date", value=datetime.now() + pd.Timedelta(days=7))
        
        st.markdown("### Items")
        
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            item_name = st.text_input("Item Name", key="po_item_name")
        with col2:
            item_qty = st.number_input("Qty", min_value=1, value=1, key="po_qty")
        with col3:
            item_cost = st.number_input("Cost ($)", min_value=0.0, value=0.0, step=0.5, key="po_cost")
        with col4:
            if st.button("Add", key="po_add"):
                if item_name and item_cost > 0:
                    if "po_items" not in st.session_state:
                        st.session_state.po_items = []
                    st.session_state.po_items.append({
                        "name": item_name,
                        "quantity": item_qty,
                        "cost": item_cost,
                        "total": item_qty * item_cost
                    })
                    st.rerun()
        
        if "po_items" not in st.session_state:
            st.session_state.po_items = []
        
        if st.session_state.po_items:
            items_df = pd.DataFrame(st.session_state.po_items)
            st.dataframe(items_df, use_container_width=True, hide_index=True)
            
            total = items_df["total"].sum()
            st.info(f"**Total Amount:** ${total:.2f}")
            
            if st.button("Clear Items", key="po_clear"):
                st.session_state.po_items = []
                st.rerun()
            
            terms = st.text_area("Terms & Conditions", value="Standard payment terms apply. Delivery within 7-14 business days.")
            
            if st.button("Generate Purchase Order", type="primary", key="po_generate"):
                data = {
                    "po_number": po_number,
                    "date": date.strftime("%Y-%m-%d"),
                    "supplier": supplier if supplier else "Unknown Supplier",
                    "delivery_date": delivery_date.strftime("%Y-%m-%d"),
                    "items": st.session_state.po_items,
                    "total": total,
                    "terms": terms
                }
                
                pdf_buffer = generate_purchase_order(data)
                download_pdf_button(
                    pdf_buffer,
                    f"purchase_order_{po_number}.pdf",
                    "Download Purchase Order"
                )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    documents_dashboard()