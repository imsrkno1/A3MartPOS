# app/utils.py
from flask import current_app
from .models import Product # Import Product model to check existing barcodes
from . import db # Import db instance
from datetime import datetime # Added for receipt date formatting

# --- PDF/Barcode Generation Imports ---
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable # Added Image, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle # Added ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT # Added TA_RIGHT
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
import io # For generating PDF/Image in memory

# --- Barcode Image Generation Imports ---
from barcode import Code128 # Or other barcode types like EAN13
from barcode.writer import ImageWriter
import os # For saving barcode images temporarily if needed (though we'll use BytesIO)

def generate_barcode_logic():
    """
    Generates the next sequential barcode based on prefix and last used number.
    Example format: A3M00001
    Returns the next barcode string or None if generation fails.
    """
    try:
        prefix = current_app.config.get('BARCODE_PREFIX', 'A3M')
        start_number = current_app.config.get('BARCODE_START_NUMBER', 1)
        padding_digits = 5 # Number of digits for the numeric part (e.g., 00001)

        last_product = Product.query.filter(Product.barcode.like(f"{prefix}%")) \
                                     .order_by(Product.id.desc()).first()

        next_num = start_number
        if last_product and last_product.barcode and last_product.barcode.startswith(prefix):
            numeric_part = last_product.barcode[len(prefix):]
            try:
                last_num = int(numeric_part)
                next_num = last_num + 1
            except ValueError:
                current_app.logger.warning(f"Could not parse numeric part of last barcode '{last_product.barcode}'. Falling back.")
                max_num_result = db.session.query(db.func.max(db.cast(db.func.substr(Product.barcode, len(prefix) + 1), db.Integer)))\
                                            .filter(Product.barcode.like(f"{prefix}%")).scalar()
                next_num = (max_num_result or 0) + 1

        while True:
            potential_barcode = f"{prefix}{next_num:0{padding_digits}d}"
            exists = Product.query.filter_by(barcode=potential_barcode).first()
            if not exists:
                return potential_barcode
            next_num += 1
            if next_num > start_number + 1000000:
                 current_app.logger.error("Barcode generation exceeded safety limit. Potential issue.")
                 return None

    except Exception as e:
        current_app.logger.error(f"Error during barcode generation: {e}")
        return None


# --- PDF/Receipt Generation Functions ---

def generate_thermal_receipt(sale_data):
    """
    Generates content suitable for a 58mm thermal printer receipt.
    Input: sale_data dictionary (e.g., from process_sale route)
    Returns: A formatted string suitable for plain text printing.
    """
    receipt_width = 32
    separator = "-" * receipt_width
    receipt_lines = []
    receipt_lines.append("A3 Mart".center(receipt_width))
    receipt_lines.append("Near KRPL, Anora Kala,Lucknow-226028".center(receipt_width))
    receipt_lines.append(separator)
    receipt_lines.append(f"Sale ID: {sale_data.get('sale_id', 'N/A')}")
    try:
        timestamp_str = sale_data.get('timestamp')
        if timestamp_str:
            dt_object = datetime.fromisoformat(timestamp_str)
            receipt_lines.append(f"Date: {dt_object.strftime('%d/%m/%y %H:%M:%S')}")
        else:
            receipt_lines.append("Date: N/A")
    except (ValueError, TypeError):
         receipt_lines.append("Date: Invalid Format")
    if sale_data.get('customer_name'):
        receipt_lines.append(f"Customer: {sale_data['customer_name']}")
    receipt_lines.append(separator)
    # Items Header (Original Simple Version)
    receipt_lines.append("{:<16} {:>4} {:>9}".format("Item", "Qty", "Total"))
    receipt_lines.append(separator)
    items = sale_data.get('items', [])
    for item in items:
         name = (item['name'][:15] + '..') if len(item['name']) > 17 else item['name']
         qty = str(item['quantity'])
         # Use net_amount for the line item total on receipt
         total = item['net_amount']
         receipt_lines.append("{:<16} {:>4} {:>9}".format(name, qty, total))
         # Optionally show discount below item if applied
         if float(item.get('discount_percent', 0)) > 0:
              receipt_lines.append(f"  (Disc: {item['discount_percent']}% -₹{item['discount_amount']})")

    receipt_lines.append(separator)
    receipt_lines.append("{:>21} {:>10}".format("Subtotal:", sale_data.get('subtotal', '0.00')))
    receipt_lines.append("{:>21} {:>10}".format("Discount:", "-" + sale_data.get('discount', '0.00')))
    receipt_lines.append("{:>21} {:>10}".format("TOTAL:", sale_data.get('total', '0.00')))
    receipt_lines.append(separator)
    receipt_lines.append(f"Paid by: {sale_data.get('payment_method', 'N/A')}")
    receipt_lines.append(separator)
    receipt_lines.append("Thank You!".center(receipt_width))
    receipt_lines.append("Visit Again!".center(receipt_width))
    receipt_lines.append("\n\n\n")
    return "\n".join(receipt_lines)


def generate_a4_invoice_pdf(sale_data):
    """
    Generates an A4 PDF invoice using ReportLab.
    Input: sale_data dictionary (as returned by process_sale)
    Returns: PDF data as bytes in a BytesIO buffer, or None on error.
    """
    buffer = io.BytesIO()
    try:
        # --- PDF Setup ---
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                leftMargin=0.75*inch, rightMargin=0.75*inch,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)
        styles = getSampleStyleSheet()
        # Add a right-aligned style for summary table
        styles.add(ParagraphStyle(name='RightAlign', parent=styles['Normal'], alignment=TA_RIGHT))
        styles.add(ParagraphStyle(name='RightAlignBold', parent=styles['h6'], alignment=TA_RIGHT))

        story = []

        # --- Header ---
        story.append(Paragraph("INVOICE", styles['h1']))
        story.append(Spacer(1, 0.2*inch))
        store_details = [
            Paragraph("<b>A3 Mart</b>", styles['Normal']),
            Paragraph("Near KRPL, Anora Kala", styles['Normal']),
            Paragraph("Lucknow, Uttar Pradesh - 226028", styles['Normal']),
            Paragraph("Phone: 8931869849", styles['Normal'])
        ]
        story.extend(store_details)
        story.append(Spacer(1, 0.2*inch))

        # --- Sale & Customer Details ---
        sale_details = []
        sale_details.append(Paragraph(f"<b>Invoice #:</b> {sale_data.get('sale_id', 'N/A')}", styles['Normal']))
        try:
            timestamp_str = sale_data.get('timestamp')
            if timestamp_str:
                dt_object = datetime.fromisoformat(timestamp_str)
                sale_details.append(Paragraph(f"<b>Date:</b> {dt_object.strftime('%d-%b-%Y %H:%M:%S')}", styles['Normal']))
            else:
                 sale_details.append(Paragraph("<b>Date:</b> N/A", styles['Normal']))
        except (ValueError, TypeError):
             sale_details.append(Paragraph("<b>Date:</b> Invalid Format", styles['Normal']))
        if sale_data.get('customer_name'):
             sale_details.append(Paragraph(f"<b>Bill To:</b> {sale_data['customer_name']}", styles['Normal']))
        story.extend(sale_details)
        story.append(Spacer(1, 0.3*inch))

        # --- Items Table ---
        # Header row
        table_header = ['#', 'Item Description', 'Qty', 'Unit Price (₹)', 'Disc %', 'Net Amount (₹)']
        table_data = [table_header]
        # Add item rows
        items = sale_data.get('items', [])
        for i, item in enumerate(items):
            table_data.append([
                str(i+1),
                Paragraph(item['name'], styles['Normal']), # Use Paragraph for wrapping
                str(item['quantity']),
                item['price'], # Unit Price (MRP)
                item['discount_percent'] + "%", # Discount Percentage
                item['net_amount'] # Net Amount for the line
            ])
        # Define column widths (adjust as needed, ensure they sum up correctly)
        col_widths = [0.4*inch, 3.0*inch, 0.6*inch, 1.0*inch, 0.8*inch, 1.2*inch]
        # Create table style
        table_style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'), # Align numeric columns right
            ('VALIGN', (0,1), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ])
        items_table = Table(table_data, colWidths=col_widths, style=table_style)
        story.append(items_table)
        story.append(Spacer(1, 0.1*inch))

        # --- Totals Section ---
        summary_data = [
            ['Subtotal:', f"₹{sale_data.get('subtotal', '0.00')}"],
            ['Discount:', f"- ₹{sale_data.get('discount', '0.00')}"],
            [Paragraph('<b>TOTAL:</b>', styles['RightAlignBold']), Paragraph(f"<b>₹{sale_data.get('total', '0.00')}</b>", styles['RightAlignBold'])]
        ]
        summary_table_style = TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TEXTCOLOR', (0,1), (0,1), colors.red), # Red discount label
            ('TEXTCOLOR', (1,1), (1,1), colors.red), # Red discount value
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ])
        # Use specific widths to align with the main table's right side
        summary_table = Table(summary_data, colWidths=[5.8*inch, 1.2*inch], style=summary_table_style)
        story.append(summary_table)
        story.append(Spacer(1, 0.2*inch))

        # --- Payment Method ---
        story.append(Paragraph(f"<b>Payment Method:</b> {sale_data.get('payment_method', 'N/A')}", styles['Normal']))
        story.append(Spacer(1, 0.5*inch))

        # --- Footer ---
        story.append(Paragraph("Thank you for your business!", styles['Normal']))

        # --- Build the PDF ---
        doc.build(story)
        buffer.seek(0)
        return buffer

    except Exception as e:
         current_app.logger.error(f"Error generating PDF invoice: {e}")
         return None


# --- Barcode Sticker Generation ---
class BarcodeSticker(Flowable):
    """ReportLab Flowable to draw a single barcode sticker."""
    def __init__(self, product_name, barcode_value, width, height):
        Flowable.__init__(self)
        self.product_name = product_name
        self.barcode_value = barcode_value
        self.width = width
        self.height = height
        self.barcode_image = self._generate_barcode_image()

    def _generate_barcode_image(self):
        """Generates barcode image in memory."""
        if not self.barcode_value: return None
        try:
            code128 = Code128(self.barcode_value, writer=ImageWriter())
            img_buffer = io.BytesIO()
            options = { 'module_height': 5.0, 'font_size': 6, 'text_distance': 2.0, 'quiet_zone': 2.0, 'write_text': True }
            code128.write(img_buffer, options=options)
            img_buffer.seek(0)
            return Image(img_buffer, width=self.width*0.9, height=self.height*0.5)
        except Exception as e:
            current_app.logger.error(f"Error generating barcode image for {self.barcode_value}: {e}")
            return None

    def wrap(self, availWidth, availHeight): return self.width, self.height

    def draw(self):
        canvas = self.canv; styles = getSampleStyleSheet()
        name_style = ParagraphStyle(name='StickerName', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER)
        p_name = Paragraph(self.product_name, name_style)
        p_name.wrapOn(canvas, self.width*0.95, self.height*0.3)
        p_name.drawOn(canvas, self.width*0.025, self.height*0.65)
        if self.barcode_image:
             img_width = self.barcode_image.drawWidth; x_pos = (self.width - img_width) / 2; y_pos = self.height * 0.1
             self.barcode_image.drawOn(canvas, x_pos, y_pos)
        else:
             barcode_text_style = ParagraphStyle(name='BarcodeText', parent=styles['Normal'], fontSize=6, alignment=TA_CENTER)
             p_barcode_error = Paragraph(f"Error: {self.barcode_value}", barcode_text_style)
             p_barcode_error.wrapOn(canvas, self.width*0.9, self.height*0.4); p_barcode_error.drawOn(canvas, self.width*0.05, self.height*0.1)

def generate_barcode_sticker_pdf(products_data):
    """
    Generates an A4 PDF sheet with barcode stickers.
    Input: products_data (list of product objects or dicts with name, barcode)
    Returns: PDF data as bytes in a BytesIO buffer, or None on error.
    """
    buffer = io.BytesIO()
    try:
        sticker_width = 2.5 * inch; sticker_height = 1.0 * inch; stickers_per_row = 3
        left_margin = 0.5 * inch; right_margin = 0.5 * inch; top_margin = 0.5 * inch; bottom_margin = 0.5 * inch
        horizontal_gap = 0.1 * inch; vertical_gap = 0.1 * inch
        page_width, page_height = A4
        usable_width = page_width - left_margin - right_margin
        col_width = (usable_width - (stickers_per_row - 1) * horizontal_gap) / stickers_per_row
        if col_width < sticker_width: sticker_width = col_width
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=left_margin, rightMargin=right_margin, topMargin=top_margin, bottomMargin=bottom_margin)
        story = []; stickers_flowables = []
        for product in products_data:
            if not product.barcode: continue
            stickers_flowables.append(BarcodeSticker(product.name, product.barcode, sticker_width, sticker_height))
        if not stickers_flowables: return None
        num_stickers = len(stickers_flowables); num_rows = (num_stickers + stickers_per_row - 1) // stickers_per_row
        simple_table_data = []; sticker_iter = iter(stickers_flowables)
        for r in range(num_rows):
             row_data = [];
             for c in range(stickers_per_row):
                 try: row_data.append(next(sticker_iter))
                 except StopIteration: row_data.append('')
             simple_table_data.append(row_data)
        simple_col_widths = [sticker_width] * stickers_per_row
        simple_table_style = TableStyle([
             ('LEFTPADDING', (0,0), (-1,-1), horizontal_gap / 2), ('RIGHTPADDING', (0,0), (-1,-1), horizontal_gap / 2),
             ('TOPPADDING', (0,0), (-1,-1), vertical_gap / 2), ('BOTTOMPADDING', (0,0), (-1,-1), vertical_gap / 2),
             ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
         ])
        sticker_table = Table(simple_table_data, colWidths=simple_col_widths, rowHeights=sticker_height, style=simple_table_style)
        story.append(sticker_table); doc.build(story); buffer.seek(0); return buffer
    except Exception as e:
         current_app.logger.error(f"Error generating barcode sticker PDF: {e}"); return None