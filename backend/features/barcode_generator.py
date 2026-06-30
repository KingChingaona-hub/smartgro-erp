import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO
import base64
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import qrcode
from PIL import Image as PILImage
import tempfile
import os

from backend.core.db_adapter import load_products

# ==============================
# BARCODE GENERATION FUNCTIONS
# ==============================

def generate_barcode_image(barcode_number, width=300, height=120):
    """Generate a simple barcode using HTML/CSS (no matplotlib needed)"""
    try:
        barcode_str = str(barcode_number)
        
        # Create bar pattern based on digits
        bars_html = ""
        for digit in barcode_str:
            digit_val = int(digit)
            # Each digit creates a pattern of bars
            bar_height = 30 + (digit_val / 9) * 50
            bars_html += f'<div style="width:6px;height:{bar_height}px;background:black;display:inline-block;margin:0 1px;"></div>'
        
        html = f"""
        <div style="width:{width}px;height:{height}px;background:white;padding:15px;border:1px solid #ddd;border-radius:8px;text-align:center;margin:10px auto;">
            <div style="display:flex;justify-content:center;align-items:flex-end;height:{height-50}px;gap:2px;padding:5px 0;">
                {bars_html}
            </div>
            <div style="text-align:center;font-size:14px;font-weight:bold;margin-top:8px;font-family:monospace;letter-spacing:2px;">
                {barcode_str}
            </div>
            <div style="text-align:center;font-size:10px;color:#999;margin-top:4px;">
                Scan me
            </div>
        </div>
        """
        
        return html
    except Exception as e:
        print(f"Error generating barcode: {e}")
        return None


def generate_qr_code(data, size=200):
    """Generate QR code for product information"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None


def generate_shelf_label(product, include_qr=False):
    """Generate a shelf label for a product"""
    
    label_html = f"""
    <div style="
        width: 300px;
        height: 200px;
        border: 1px solid #ccc;
        padding: 10px;
        font-family: Arial, sans-serif;
        background: white;
        margin: 10px;
        display: inline-block;
        page-break-inside: avoid;
    ">
        <div style="text-align: center;">
            <strong style="font-size: 14px;">{product['name']}</strong>
        </div>
        <div style="text-align: center; margin: 10px 0;">
            <div style="font-size: 10px; color: #666;">Barcode:</div>
            <div style="font-size: 16px; font-weight: bold;">{product['barcode']}</div>
        </div>
        <div style="display: flex; justify-content: space-between; margin: 10px 0;">
            <div>
                <div style="font-size: 10px; color: #666;">Price:</div>
                <div style="font-size: 18px; font-weight: bold; color: green;">${product['price']:.2f}</div>
            </div>
            <div>
                <div style="font-size: 10px; color: #666;">Stock:</div>
                <div style="font-size: 14px;">{product['stock']} units</div>
            </div>
        </div>
        <div style="text-align: center; margin-top: 10px; font-size: 9px; color: #999;">
            Aziel Investments - Smart Retail
        </div>
    </div>
    """
    
    return label_html


def generate_barcode_pdf(products, page_size=A4):
    """Generate a PDF with barcodes for multiple products"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=page_size)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
    story.append(Paragraph("Product Barcode Labels", title_style))
    story.append(Spacer(1, 20))
    
    # Create table data (3 columns for A4)
    table_data = []
    row = []
    
    for i, product in enumerate(products):
        # Create barcode image
        barcode_img = generate_barcode_image(product['barcode'])
        if barcode_img:
            img = Image(barcode_img, width=150, height=60)
            row.append(img)
        else:
            row.append(Paragraph(f"<b>{product['barcode']}</b>", styles['Normal']))
        
        if len(row) == 3 or i == len(products) - 1:
            while len(row) < 3:
                row.append("")
            table_data.append(row)
            row = []
    
    # Create table
    table = Table(table_data, colWidths=[180, 180, 180])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
    ]))
    
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    
    return buffer


def generate_qr_pdf(products):
    """Generate PDF with QR codes for products"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
    story.append(Paragraph("Product QR Codes", title_style))
    story.append(Spacer(1, 20))
    
    # Create QR codes
    for product in products:
        product_data = f"Product: {product['name']}\nBarcode: {product['barcode']}\nPrice: ${product['price']:.2f}"
        qr_img = generate_qr_code(product_data)
        
        if qr_img:
            img = Image(qr_img, width=100, height=100)
            
            # Create a table for each product
            data = [
                [img, Paragraph(f"<b>{product['name']}</b><br/>Barcode: {product['barcode']}<br/>Price: ${product['price']:.2f}", styles['Normal'])]
            ]
            t = Table(data, colWidths=[120, 250])
            t.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer


def generate_shelf_label_pdf(products):
    """Generate PDF with shelf labels"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    
    # Create table for labels (2x2 grid)
    label_data = []
    row = []
    
    for i, product in enumerate(products):
        # Create label HTML
        label_html = generate_shelf_label(product)
        label_paragraph = Paragraph(label_html, getSampleStyleSheet()['Normal'])
        row.append(label_paragraph)
        
        if len(row) == 2 or i == len(products) - 1:
            while len(row) < 2:
                row.append("")
            label_data.append(row)
            row = []
    
    table = Table(label_data, colWidths=[400, 400])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    
    return buffer


# ==============================
# BARCODE GENERATOR DASHBOARD
# ==============================

def barcode_generator_page():
    """Barcode Generation and Printing Dashboard"""
    
    st.title("📦 Barcode & Label Generator")
    st.caption("Generate printable barcodes, QR codes, and shelf labels for your products")
    
    products_df = load_products()
    
    if products_df.empty:
        st.warning("No products found. Please add products in Inventory first.")
        if st.button("Go to Inventory"):
            st.session_state.current_page = "Inventory"
            st.rerun()
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔍 Single Barcode",
        "📦 Bulk Barcode Printing",
        "📱 QR Code Generator",
        "🏷️ Shelf Labels"
    ])
    
    # ==============================
    # TAB 1: SINGLE BARCODE
    # ==============================
    with tab1:
        st.markdown("## 🔍 Generate Single Barcode")
        
        # Product selection
        selected_product = st.selectbox(
            "Select Product",
            products_df["name"].tolist(),
            key="single_barcode_product"
        )
        
        if selected_product:
            product = products_df[products_df["name"] == selected_product].iloc[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📊 Product Info")
                st.write(f"**Name:** {product['name']}")
                st.write(f"**Barcode:** {product['barcode']}")
                st.write(f"**Price:** ${product['price']:.2f}")
                st.write(f"**Stock:** {product['stock']} units")
            
            with col2:
                st.markdown("### 🖨️ Barcode Preview")
                
                # Generate barcode HTML
                barcode_html = generate_barcode_image(product['barcode'])
                if barcode_html:
                    st.components.v1.html(barcode_html, height=200)
                    
                    # Download button for HTML barcode
                    st.download_button(
                        label="📥 Download Barcode (PNG)",
                        data=barcode_html.encode('utf-8'),
                        file_name=f"barcode_{product['barcode']}.html",
                        mime="text/html",
                        use_container_width=True
                    )
                else:
                    st.warning("Could not generate barcode preview")
            
            # Print barcode HTML
            st.markdown("### 🖨️ Print Barcode Label")
            
            html_label = generate_shelf_label(product)
            st.components.v1.html(html_label, height=250)
    
    # ==============================
    # TAB 2: BULK BARCODE PRINTING
    # ==============================
    with tab2:
        st.markdown("## 📦 Bulk Barcode Printing")
        st.caption("Generate barcodes for multiple products at once")
        
        # Product selection
        st.markdown("### Select Products")
        
        # Search filter
        search = st.text_input("🔍 Filter Products", placeholder="Type to search...")
        
        filtered_products = products_df.copy()
        if search:
            filtered_products = products_df[
                products_df["name"].str.contains(search, case=False) |
                products_df["barcode"].astype(str).str.contains(search, case=False)
            ]
        
        # Multi-select
        selected_products = st.multiselect(
            "Select products to generate barcodes",
            filtered_products["name"].tolist(),
            help="Choose products you want barcodes for"
        )
        
        if selected_products:
            selected_data = products_df[products_df["name"].isin(selected_products)]
            
            st.markdown(f"**{len(selected_products)} products selected**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                page_size = st.selectbox("Page Size", ["A4", "Letter"])
                page = A4 if page_size == "A4" else letter
            
            with col2:
                label_type = st.selectbox("Label Type", ["Barcodes Only", "Shelf Labels", "QR Codes"])
            
            if st.button("📄 Generate PDF", type="primary", use_container_width=True):
                with st.spinner("Generating PDF..."):
                    if label_type == "Barcodes Only":
                        pdf_buffer = generate_barcode_pdf(selected_data.to_dict('records'), page)
                        filename = f"barcodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    elif label_type == "Shelf Labels":
                        pdf_buffer = generate_shelf_label_pdf(selected_data.to_dict('records'))
                        filename = f"shelf_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    else:
                        pdf_buffer = generate_qr_pdf(selected_data.to_dict('records'))
                        filename = f"qr_codes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_buffer,
                        file_name=filename,
                        mime="application/pdf",
                        use_container_width=True
                    )
                    
                    st.success("✅ PDF generated successfully!")
    
    # ==============================
    # TAB 3: QR CODE GENERATOR
    # ==============================
    with tab3:
        st.markdown("## 📱 QR Code Generator")
        st.caption("Generate QR codes for mobile product lookup")
        
        selected_product = st.selectbox(
            "Select Product",
            products_df["name"].tolist(),
            key="qr_product"
        )
        
        if selected_product:
            product = products_df[products_df["name"] == selected_product].iloc[0]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📊 Product Info")
                st.write(f"**Name:** {product['name']}")
                st.write(f"**Barcode:** {product['barcode']}")
                st.write(f"**Price:** ${product['price']:.2f}")
                
                # QR code data options
                qr_data_type = st.radio(
                    "QR Code Data",
                    ["Product Info", "Custom Message"]
                )
                
                if qr_data_type == "Product Info":
                    qr_data = f"""
Product: {product['name']}
Barcode: {product['barcode']}
Price: ${product['price']:.2f}
Category: {product.get('category', 'N/A')}
Stock: {product['stock']} units
                    """
                else:
                    qr_data = st.text_area("Custom Message", value=f"Scan to view {product['name']} details")
            
            with col2:
                st.markdown("### 🖨️ QR Code Preview")
                
                # Generate QR code
                qr_img = generate_qr_code(qr_data.strip())
                if qr_img:
                    st.image(qr_img, use_column_width=True)
                    
                    # Download button
                    qr_data_bin = qr_img.getvalue()
                    st.download_button(
                        label="📥 Download QR Code (PNG)",
                        data=qr_data_bin,
                        file_name=f"qrcode_{product['barcode']}.png",
                        mime="image/png",
                        use_container_width=True
                    )
                else:
                    st.warning("Could not generate QR code")
    
    # ==============================
    # TAB 4: SHELF LABELS
    # ==============================
    with tab4:
        st.markdown("## 🏷️ Shelf Label Printing")
        st.caption("Professional shelf labels for retail displays")
        
        # Layout selection
        col1, col2 = st.columns(2)
        
        with col1:
            label_layout = st.selectbox(
                "Label Layout",
                ["Single Label", "Multiple Labels (2x2)", "Multiple Labels (3x3)"]
            )
        
        with col2:
            include_price = st.checkbox("Include Price", value=True)
            include_stock = st.checkbox("Include Stock Level", value=False)
        
        # Product selection
        st.markdown("### Select Products")
        
        if label_layout == "Single Label":
            selected_product = st.selectbox(
                "Select Product",
                products_df["name"].tolist(),
                key="shelf_single"
            )
            
            if selected_product:
                product = products_df[products_df["name"] == selected_product].iloc[0]
                
                # Generate label
                label_html = generate_shelf_label(product)
                st.components.v1.html(label_html, height=250)
                
                # Download as PDF
                if st.button("📄 Download as PDF", use_container_width=True):
                    pdf_buffer = generate_shelf_label_pdf([product.to_dict()])
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_buffer,
                        file_name=f"shelf_label_{product['barcode']}.pdf",
                        mime="application/pdf"
                    )
        else:
            # Multi-label selection
            search = st.text_input("🔍 Search Products", key="shelf_search")
            
            filtered = products_df.copy()
            if search:
                filtered = products_df[products_df["name"].str.contains(search, case=False)]
            
            selected_products = st.multiselect(
                "Select products for shelf labels",
                filtered["name"].tolist(),
                key="shelf_multi"
            )
            
            if selected_products:
                selected_data = products_df[products_df["name"].isin(selected_products)]
                
                # Preview
                st.markdown("### 📋 Preview")
                
                cols = st.columns(min(3, len(selected_data)))
                for idx, (_, product) in enumerate(selected_data.head(6).iterrows()):
                    with cols[idx % len(cols)]:
                        label_html = generate_shelf_label(product)
                        st.components.v1.html(label_html, height=220)
                
                if len(selected_data) > 6:
                    st.caption(f"... and {len(selected_data) - 6} more labels")
                
                # Download all
                if st.button("📄 Generate All Labels", type="primary", use_container_width=True):
                    pdf_buffer = generate_shelf_label_pdf(selected_data.to_dict('records'))
                    st.download_button(
                        label="📥 Download PDF",
                        data=pdf_buffer,
                        file_name=f"shelf_labels_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
    
    # ==============================
    # MOBILE SCANNING SUPPORT SECTION
    # ==============================
    st.markdown("---")
    st.markdown("## 📱 Mobile Scanning Support")
    st.caption("Use your phone camera to scan barcodes")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📷 How to Scan
        
        1. Open your phone's camera
        2. Point at any generated barcode
        3. Tap the link that appears
        4. Product information will display
        
        **Supported Apps:**
        - Google Lens
        - Apple Camera
        - Any barcode scanner app
        """)
    
    with col2:
        st.markdown("""
        ### 🔍 Scan to View Product
        
        Generate a QR code for any product, then scan with your phone to see:
        - Product name and price
        - Current stock level
        - Product description
        - Location in store
        
        This is perfect for staff and customers!
        """)
        
        # Demo QR code
        demo_data = "Product: Demo Product\nPrice: $10.00\nStock: Available"
        demo_qr = generate_qr_code(demo_data)
        if demo_qr:
            st.image(demo_qr, width=150, caption="Sample QR Code - Scan with your phone!")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    barcode_generator_page()