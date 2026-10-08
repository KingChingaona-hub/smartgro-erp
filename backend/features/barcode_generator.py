# backend/features/barcode_generator.py
# Barcode & Label Generator — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Generated PDFs carry a branch header line. CSV/filename exports include the
# branch code so HO and NAT outputs don't collide on the owner's desktop.

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO
import base64
import re
from reportlab.lib.pagesizes import A4, letter
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm, inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import qrcode
from PIL import Image as PILImage
import tempfile
import os

from backend.core.db_adapter import load_products, load_branches


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_all_branches(branch_id):
    return isinstance(branch_id, str) and branch_id.upper() == ALL_BRANCHES


def _load_scoped(loader, branch_id, **kwargs):
    if _is_all_branches(branch_id):
        try:
            bdf = load_branches()
        except Exception:
            bdf = pd.DataFrame()
        if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
            try:
                return loader(**kwargs)
            except Exception:
                return pd.DataFrame()
        frames = []
        for bid in bdf["branch_id"].astype(str).tolist():
            try:
                df = loader(branch_id=bid, **kwargs)
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    try:
        return loader(branch_id=branch_id, **kwargs)
    except TypeError:
        try:
            return loader(**kwargs)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _branch_label(branch_id):
    if _is_all_branches(branch_id):
        return "All Branches"
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                return f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()
    except Exception:
        pass
    return str(branch_id)


def _branch_slug(branch_id):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_").upper() or "HO"


def _branch_scope_selector(branches_df):
    role = st.session_state.get("role", "cashier")
    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})"
            for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            options,
            key="barcode_gen_branch_scope",
            help="Owners may generate labels for any branch or all at once.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Barcode generator locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# BARCODE IMAGE (HTML/CSS)
# ==============================
def generate_barcode_image(barcode_number, width=300, height=120, branch_label=""):
    """Return HTML for a rendered barcode. `branch_label` adds a subtitle."""
    try:
        barcode_str = str(barcode_number)
        bars = ""
        for digit in barcode_str:
            digit_val = int(digit) if digit.isdigit() else 0
            bar_height = 30 + (digit_val / 9) * 50
            bars += (
                f'<div style="width:6px;height:{bar_height}px;'
                f'background:black;display:inline-block;margin:0 1px;"></div>'
            )

        subtitle = (
            f'<div style="font-size:11px;color:#666;margin-top:2px;">{branch_label}</div>'
            if branch_label else ""
        )

        html = f"""
        <div style="background:white;padding:20px;border:1px solid #ddd;border-radius:8px;text-align:center;margin:10px 0;">
            <div style="display:flex;justify-content:center;align-items:flex-end;height:80px;gap:2px;padding:5px 0;">
                {bars}
            </div>
            <div style="font-size:16px;font-weight:bold;font-family:monospace;letter-spacing:2px;margin-top:10px;">
                {barcode_str}
            </div>
            {subtitle}
            <div style="font-size:10px;color:#999;margin-top:4px;">
                Scan me
            </div>
        </div>
        """
        return html
    except Exception as e:
        print(f"[barcode_generator] error generating barcode HTML: {e}")
        return None


def generate_qr_code(data, size=200):
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
        print(f"[barcode_generator] error generating QR: {e}")
        return None


def generate_shelf_label(product, include_qr=False, branch_label=""):
    """Return HTML for a shelf label. Branch label rendered under the barcode."""
    branch_line = (
        f'<div style="font-size: 9px; color: #666; margin-top: 4px;">{branch_label}</div>'
        if branch_label else ""
    )
    return f"""
    <div style="
        width: 300px; height: 200px; border: 1px solid #ccc; padding: 10px;
        font-family: Arial, sans-serif; background: white; margin: 10px;
        display: inline-block; page-break-inside: avoid;
    ">
        <div style="text-align: center;">
            <strong style="font-size: 14px;">{product['name']}</strong>
        </div>
        <div style="text-align: center; margin: 10px 0;">
            <div style="font-size: 10px; color: #666;">Barcode:</div>
            <div style="font-size: 16px; font-weight: bold;">{product['barcode']}</div>
            {branch_line}
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


# ==============================
# PDF GENERATORS
# ==============================
def _pdf_header(styles, title, branch_label):
    """Return a list of flowables for the PDF header with a branch line."""
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1
    )
    branch_style = ParagraphStyle(
        'BranchLine', parent=styles['Normal'], fontSize=11, alignment=1,
        textColor=colors.HexColor('#1a237e'),
    )
    generated_style = ParagraphStyle(
        'Generated', parent=styles['Normal'], fontSize=9, alignment=1,
        textColor=colors.grey,
    )
    return [
        Paragraph(title, title_style),
        Paragraph(f"Branch: {branch_label}", branch_style),
        Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            generated_style,
        ),
        Spacer(1, 12),
    ]


def generate_barcode_pdf(products, page_size=A4, branch_label="", branch_code="HO"):
    """PDF with one barcode per product, arranged in a grid."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=page_size)
    story = []
    styles = getSampleStyleSheet()

    story.extend(_pdf_header(styles, "Product Barcode Labels", branch_label))

    table_data = []
    row = []

    for i, product in enumerate(products):
        barcode_html = generate_barcode_image(product['barcode'])
        if barcode_html:
            row.append(Paragraph(f"<b>{product['barcode']}</b>", styles['Normal']))
        else:
            row.append(Paragraph(f"<b>{product['barcode']}</b>", styles['Normal']))

        if len(row) == 3 or i == len(products) - 1:
            while len(row) < 3:
                row.append("")
            table_data.append(row)
            row = []

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


def generate_qr_pdf(products, branch_label="", branch_code="HO"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()

    story.extend(_pdf_header(styles, "Product QR Codes", branch_label))

    for product in products:
        product_data = (
            f"Branch: {branch_label}\n"
            f"Product: {product['name']}\n"
            f"Barcode: {product['barcode']}\n"
            f"Price: ${product['price']:.2f}"
        )
        qr_img = generate_qr_code(product_data)
        if qr_img:
            img = Image(qr_img, width=100, height=100)
            data = [[
                img,
                Paragraph(
                    f"<b>{product['name']}</b><br/>"
                    f"Barcode: {product['barcode']}<br/>"
                    f"Price: ${product['price']:.2f}<br/>"
                    f"<i>{branch_label}</i>",
                    styles['Normal'],
                ),
            ]]
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


def generate_shelf_label_pdf(products, branch_label="", branch_code="HO"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()

    story.extend(_pdf_header(styles, "Shelf Labels", branch_label))

    label_data = []
    row = []
    for i, product in enumerate(products):
        label_html = generate_shelf_label(product, branch_label=branch_label)
        # Strip the outer <div> styling for reportlab — pass as text
        row.append(Paragraph(
            f"<b>{product['name']}</b><br/>"
            f"Barcode: {product['barcode']}<br/>"
            f"<i>{branch_label}</i><br/>"
            f"Price: ${product['price']:.2f}<br/>"
            f"Stock: {product['stock']}",
            styles['Normal'],
        ))
        if len(row) == 2 or i == len(products) - 1:
            while len(row) < 2:
                row.append("")
            label_data.append(row)
            row = []

    table = Table(label_data, colWidths=[400, 400])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer


# ==============================
# DASHBOARD
# ==============================
def barcode_generator_page(branch_id=None):
    st.title("Barcode & Label Generator")
    st.caption("Generate printable barcodes, QR codes, and shelf labels — branch-scoped")

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Generating for: **{branch_label}**")

    products_df = _load_scoped(load_products, branch_id)

    if products_df is None or products_df.empty:
        st.warning(f"No products found for {branch_label}. Add products in Inventory first.")
        if st.button("Go to Inventory", key=f"barcode_goto_inv_{branch_id}"):
            st.session_state.current_page = "Inventory"
            st.rerun()
        return

    branch_code = _branch_slug(branch_id)

    tab1, tab2, tab3, tab4 = st.tabs([
        "Single Barcode",
        "Bulk Barcode Printing",
        "QR Code Generator",
        "Shelf Labels",
    ])

    # ==============================
    # TAB 1: SINGLE BARCODE
    # ==============================
    with tab1:
        st.markdown("## Generate Single Barcode")

        selected_product = st.selectbox(
            "Select Product",
            products_df["name"].tolist(),
            key=f"single_barcode_product_{branch_id}",
        )

        if selected_product:
            product = products_df[products_df["name"] == selected_product].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Product Info")
                st.write(f"**Name:** {product['name']}")
                st.write(f"**Barcode:** {product['barcode']}")
                st.write(f"**Price:** ${product['price']:.2f}")
                st.write(f"**Stock:** {product['stock']} units")
                st.caption(f"Branch: {branch_label}")

            with col2:
                st.markdown("### Barcode Preview")
                barcode_html = generate_barcode_image(
                    product['barcode'], branch_label=branch_label
                )
                if barcode_html:
                    st.markdown(barcode_html, unsafe_allow_html=True)
                    st.download_button(
                        label="Download Barcode (HTML)",
                        data=barcode_html.encode('utf-8'),
                        file_name=f"barcode_{branch_code}_{product['barcode']}.html",
                        mime="text/html",
                        use_container_width=True,
                        key=f"dl_single_html_{branch_id}",
                    )
                else:
                    st.warning("Could not generate barcode preview")

            st.markdown("### Print Barcode Label")
            html_label = generate_shelf_label(product, branch_label=branch_label)
            st.components.v1.html(html_label, height=250)

    # ==============================
    # TAB 2: BULK BARCODE PRINTING
    # ==============================
    with tab2:
        st.markdown("## Bulk Barcode Printing")
        st.caption(f"Generate barcodes for multiple products — {branch_label}")

        search = st.text_input(
            "Filter Products",
            placeholder="Type to search...",
            key=f"bulk_search_{branch_id}",
        )

        filtered_products = products_df.copy()
        if search:
            filtered_products = products_df[
                products_df["name"].str.contains(search, case=False)
                | products_df["barcode"].astype(str).str.contains(search, case=False)
            ]

        selected_products = st.multiselect(
            "Select products to generate barcodes",
            filtered_products["name"].tolist(),
            help="Choose products you want barcodes for",
            key=f"bulk_selected_{branch_id}",
        )

        if selected_products:
            selected_data = products_df[products_df["name"].isin(selected_products)]

            st.markdown(f"**{len(selected_products)} products selected for {branch_label}**")

            col1, col2 = st.columns(2)
            with col1:
                page_size = st.selectbox(
                    "Page Size", ["A4", "Letter"], key=f"bulk_page_{branch_id}"
                )
                page = A4 if page_size == "A4" else letter
            with col2:
                label_type = st.selectbox(
                    "Label Type",
                    ["Barcodes Only", "Shelf Labels", "QR Codes"],
                    key=f"bulk_type_{branch_id}",
                )

            if st.button("Generate PDF", type="primary", use_container_width=True,
                         key=f"bulk_gen_{branch_id}"):
                with st.spinner(f"Generating PDF for {branch_label}..."):
                    records = selected_data.to_dict('records')
                    if label_type == "Barcodes Only":
                        pdf_buffer = generate_barcode_pdf(
                            records, page,
                            branch_label=branch_label, branch_code=branch_code,
                        )
                        filename = f"barcodes_{branch_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    elif label_type == "Shelf Labels":
                        pdf_buffer = generate_shelf_label_pdf(
                            records, branch_label=branch_label, branch_code=branch_code,
                        )
                        filename = f"shelf_labels_{branch_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    else:
                        pdf_buffer = generate_qr_pdf(
                            records, branch_label=branch_label, branch_code=branch_code,
                        )
                        filename = f"qr_codes_{branch_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

                    st.download_button(
                        label="Download PDF",
                        data=pdf_buffer,
                        file_name=filename,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"bulk_dl_{branch_id}",
                    )
                    st.success(f"PDF generated for {branch_label}!")

    # ==============================
    # TAB 3: QR CODES
    # ==============================
    with tab3:
        st.markdown("## QR Code Generator")
        st.caption("QR codes for mobile product lookup")

        selected_product = st.selectbox(
            "Select Product",
            products_df["name"].tolist(),
            key=f"qr_product_{branch_id}",
        )

        if selected_product:
            product = products_df[products_df["name"] == selected_product].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Product Info")
                st.write(f"**Name:** {product['name']}")
                st.write(f"**Barcode:** {product['barcode']}")
                st.write(f"**Price:** ${product['price']:.2f}")
                st.caption(f"Branch: {branch_label}")

                qr_data_type = st.radio(
                    "QR Code Data",
                    ["Product Info", "Custom Message"],
                    key=f"qr_data_type_{branch_id}",
                )

                if qr_data_type == "Product Info":
                    qr_data = (
                        f"Branch: {branch_label}\n"
                        f"Product: {product['name']}\n"
                        f"Barcode: {product['barcode']}\n"
                        f"Price: ${product['price']:.2f}\n"
                        f"Category: {product.get('category', 'N/A')}\n"
                        f"Stock: {product['stock']} units"
                    )
                else:
                    qr_data = st.text_area(
                        "Custom Message",
                        value=f"Scan to view {product['name']} details",
                        key=f"qr_custom_{branch_id}",
                    )
            with col2:
                st.markdown("### QR Code Preview")
                qr_img = generate_qr_code(qr_data.strip())
                if qr_img:
                    st.image(qr_img, use_column_width=True)
                    qr_bytes = qr_img.getvalue()
                    st.download_button(
                        label="Download QR Code (PNG)",
                        data=qr_bytes,
                        file_name=f"qrcode_{branch_code}_{product['barcode']}.png",
                        mime="image/png",
                        use_container_width=True,
                        key=f"qr_dl_{branch_id}",
                    )
                else:
                    st.warning("Could not generate QR code")

    # ==============================
    # TAB 4: SHELF LABELS
    # ==============================
    with tab4:
        st.markdown("## Shelf Label Printing")
        st.caption(f"Retail shelf labels — {branch_label}")

        col1, col2 = st.columns(2)
        with col1:
            label_layout = st.selectbox(
                "Label Layout",
                ["Single Label", "Multiple Labels (2x2)", "Multiple Labels (3x3)"],
                key=f"shelf_layout_{branch_id}",
            )
        with col2:
            include_price = st.checkbox(
                "Include Price", value=True, key=f"shelf_price_{branch_id}"
            )
            include_stock = st.checkbox(
                "Include Stock Level", value=False, key=f"shelf_stock_{branch_id}"
            )

        if label_layout == "Single Label":
            selected_product = st.selectbox(
                "Select Product",
                products_df["name"].tolist(),
                key=f"shelf_single_{branch_id}",
            )
            if selected_product:
                product = products_df[products_df["name"] == selected_product].iloc[0]
                label_html = generate_shelf_label(product, branch_label=branch_label)
                st.components.v1.html(label_html, height=250)

                if st.button("Download as PDF", use_container_width=True,
                             key=f"shelf_dl_{branch_id}"):
                    pdf_buffer = generate_shelf_label_pdf(
                        [product.to_dict()],
                        branch_label=branch_label, branch_code=branch_code,
                    )
                    st.download_button(
                        label="Download PDF",
                        data=pdf_buffer,
                        file_name=f"shelf_label_{branch_code}_{product['barcode']}.pdf",
                        mime="application/pdf",
                        key=f"shelf_dl_btn_{branch_id}",
                    )
        else:
            search = st.text_input(
                "Search Products", key=f"shelf_search_{branch_id}"
            )
            filtered = products_df.copy()
            if search:
                filtered = products_df[
                    products_df["name"].str.contains(search, case=False)
                ]

            selected_products = st.multiselect(
                "Select products for shelf labels",
                filtered["name"].tolist(),
                key=f"shelf_multi_{branch_id}",
            )

            if selected_products:
                selected_data = products_df[products_df["name"].isin(selected_products)]

                st.markdown("### Preview")
                cols = st.columns(min(3, len(selected_data)))
                for idx, (_, product) in enumerate(selected_data.head(6).iterrows()):
                    with cols[idx % len(cols)]:
                        label_html = generate_shelf_label(
                            product, branch_label=branch_label
                        )
                        st.components.v1.html(label_html, height=220)
                if len(selected_data) > 6:
                    st.caption(f"... and {len(selected_data) - 6} more labels")

                if st.button("Generate All Labels", type="primary",
                             use_container_width=True,
                             key=f"shelf_gen_all_{branch_id}"):
                    pdf_buffer = generate_shelf_label_pdf(
                        selected_data.to_dict('records'),
                        branch_label=branch_label, branch_code=branch_code,
                    )
                    st.download_button(
                        label="Download PDF",
                        data=pdf_buffer,
                        file_name=f"shelf_labels_{branch_code}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"shelf_gen_all_dl_{branch_id}",
                    )

    # ==============================
    # MOBILE SCANNING SUPPORT
    # ==============================
    st.markdown("---")
    st.markdown("## Mobile Scanning Support")
    st.caption("Use your phone camera to scan barcodes")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        ### How to Scan — {branch_label}

        1. Open your phone's camera
        2. Point at any generated barcode
        3. Tap the link that appears
        4. Product information for {branch_label} will display

        **Supported Apps:**
        - Google Lens
        - Apple Camera
        - Any barcode scanner app
        """)
    with col2:
        st.markdown("### Scan to View Product")
        st.markdown(
            f"Generate a QR code for any {branch_label} product, then scan with your phone."
        )
        demo_data = f"Branch: {branch_label}\nProduct: Demo\nPrice: $10.00"
        demo_qr = generate_qr_code(demo_data)
        if demo_qr:
            st.image(demo_qr, width=150,
                     caption=f"Sample QR — scans to a {branch_label} product")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    barcode_generator_page()