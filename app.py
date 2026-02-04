"""
EMPLOYEE'S EXACT CODE - NO MODIFICATIONS
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import xlsxwriter
import requests
from io import BytesIO
import re
from datetime import datetime
import concurrent.futures
from PIL import Image as PilImage
from PIL import ImageOps

app = Flask(__name__)
CORS(app)

# EMPLOYEE'S EXACT SETTINGS
TARGET_W = 150
TARGET_H = 150
COL_WIDTH_UNITS = 22

BRAND_IMAGE_PREFIX = {
    'NAUTICA': 'NA', 'NE': 'NA', 'NA': 'NA',
    'DKNY': 'DK', 'DK': 'DK',
    'EB': 'EB',
    'REEBOK': 'RB', 'RB': 'RB',
    'VINCE': 'VC', 'VC': 'VC',
    'BEN': 'BE', 'BE': 'BE', 'BS': 'BE',
    'USPA': 'US', 'US': 'US',
    'CHAPS': 'CH', 'CH': 'CH',
    'LUCKY': 'LB', 'LB': 'LB',
    'JNY': 'JN', 'JN': 'JN',
    'BEENE': 'GB', 'GB': 'GB',
    'NICOLE': 'NM', 'NM': 'NM',
    'SHAQ': 'SQ', 'SH': 'SQ',
    'TAYION': 'TY', 'TA': 'TY',
    'STRAHAN': 'MS', 'MS': 'MS',
    'VD': 'VD',
    'VERSA': 'VR',
    'AMERICA': 'AC', 'AC': 'AC',
    'BLO': 'BL',
    'DN': 'D9',
    'CK': 'CK', 'CHEROKEE': 'CK',
    'MSC': 'MSC'
}

STYLE_CONFIG = {
    'header_bg': '#ADD8E6',
    'header_text': '#000000',
    'row_bg_odd': '#FFFFFF',
    'row_bg_even': '#F0F4F8',
    'border_color': '#000000',
    'font_name': 'Calibri'
}

def extract_image_code(sku, brand_abbr):
    prefix = BRAND_IMAGE_PREFIX.get(brand_abbr, brand_abbr[:2])
    numbers = re.findall(r'\d+', str(sku))
    if numbers:
        main_number = max(numbers, key=len)
        # Pad to 3 digits with leading zeros
        padded_number = main_number.zfill(3)
        return f"{prefix}_{padded_number}"
    return f"{prefix}_{sku}"

def get_image_url(item, s3_base_url):
    brand_abbr = item['brand_abbr']
    
    # S3 folder mapping
    folder_mapping = {
        'EB': 'EDDIE+BAUER',
        'US': 'US+POLO',
        'VC': 'VINCE+CAMUTO',
        'LB': 'LUCKY+BRAND',
        'BE': 'BEN+SHERMAN',
        'GB': 'GEOFFREY+BEENE',
        'NM': 'NICOLE+MILLER',
        'AC': 'AMERICAN+CREW',
        'TA': 'TAVION',
        'VD': 'Von+Dutch',
        'NE': 'NAUTICA',
        'NA': 'NAUTICA',
        'DK': 'DKNY',
        'DKNY': 'DKNY',
        'RB': 'REEBOK',
        'CH': 'CHAPS',
        'JN': 'JONES+NEW+YORK',
        'SH': 'SHAQ',
        'MS': 'MICHAEL+STRAHAN',
        'CK': 'CHEROKEE',
        'MSC': 'MISCELLANEOUS'
    }
    
    folder_name = folder_mapping.get(brand_abbr, brand_abbr)
    image_code = extract_image_code(item['sku'], brand_abbr)
    
    # Return list of URLs to try (jpg, jpeg, png)
    return [
        f"{s3_base_url}/{folder_name}/{image_code}.jpg",
        f"{s3_base_url}/{folder_name}/{image_code}.jpeg",
        f"{s3_base_url}/{folder_name}/{image_code}.png"
    ]

def process_single_image(url, target_width, target_height):
    """EMPLOYEE'S EXACT IMAGE PROCESSING CODE"""
    if not (isinstance(url, str) and url.startswith('http')):
        return None
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        content_type = response.headers.get('Content-Type', '').lower()
        if 'image' not in content_type:
            return None
        if response.status_code != 200:
            return None
            
        image_data = BytesIO(response.content)
        
        with PilImage.open(image_data) as im:
            im = ImageOps.exif_transpose(im)
            
            im.thumbnail((target_width * 2, target_height * 2), PilImage.Resampling.LANCZOS)
            
            output_format = "PNG"
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                output_format = "PNG"
            else:
                if im.mode != "RGB":
                    im = im.convert("RGB")
                output_format = "JPEG"
            
            processed_image_data = BytesIO()
            im.save(processed_image_data, format=output_format, quality=85, optimize=True)
            processed_image_data.seek(0)
            
            orig_w, orig_h = im.size
        
        width_ratio = target_width / orig_w
        height_ratio = target_height / orig_h
        scale_factor = min(width_ratio, height_ratio)
        
        final_w = orig_w * scale_factor
        final_h = orig_h * scale_factor
        
        x_offset = (target_width - final_w) / 2
        y_offset = (target_height - final_h) / 2
        
        return {
            'image_data': processed_image_data,
            'x_scale': scale_factor,
            'y_scale': scale_factor,
            'x_offset': x_offset,
            'y_offset': y_offset,
            'object_position': 1,
            'url': url
        }
    except Exception:
        return None

def try_multiple_image_urls(urls, target_width, target_height):
    """Try multiple image URLs (jpg, jpeg, png) until one works"""
    for url in urls:
        result = process_single_image(url, target_width, target_height)
        if result:
            return result
    return None

def create_excel_with_images(data, s3_base_url, title="Inventory"):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    workbook.set_properties({
        'title': 'Versa Inventory Export',
        'author': 'Versa Inventory System',
        'created': datetime.now(),
    })
    
    worksheet = workbook.add_worksheet(title[:31])
    
    # Formats
    fmt_header = workbook.add_format({
        'bold': True,
        'font_name': STYLE_CONFIG['font_name'],
        'font_size': 11,
        'bg_color': STYLE_CONFIG['header_bg'],
        'font_color': STYLE_CONFIG['header_text'],
        'border': 1,
        'border_color': STYLE_CONFIG['border_color'],
        'align': 'center',
        'valign': 'vcenter'
    })
    
    base_props = {
        'font_name': STYLE_CONFIG['font_name'],
        'font_size': 10,
        'text_wrap': True,
        'valign': 'vcenter',
        'align': 'center',
        'border': 1,
        'border_color': STYLE_CONFIG['border_color']
    }
    
    fmt_cell_odd = workbook.add_format({**base_props, 'bg_color': STYLE_CONFIG['row_bg_odd']})
    fmt_cell_even = workbook.add_format({**base_props, 'bg_color': STYLE_CONFIG['row_bg_even']})
    
    # Number format with commas
    fmt_number_odd = workbook.add_format({
        **base_props, 
        'bg_color': STYLE_CONFIG['row_bg_odd'],
        'num_format': '#,##0'
    })
    fmt_number_even = workbook.add_format({
        **base_props, 
        'bg_color': STYLE_CONFIG['row_bg_even'],
        'num_format': '#,##0'
    })
    
    worksheet.hide_gridlines(2)
    worksheet.freeze_panes(1, 0)
    
    # Headers - Production focused columns
    headers = ['IMAGE', 'SKU', 'Brand', 'Production #', 'PO Name', 'Ex-Factory Date (ETD)', 
               'Arrival Date', 'Fit', 'Fabric Code', 'Fabrication', 'Ship Units']
    
    worksheet.set_row(0, 25)
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header, fmt_header)
    
    # Column widths
    worksheet.set_column(0, 0, COL_WIDTH_UNITS)  # Image
    worksheet.set_column(1, 1, 20)                # SKU
    worksheet.set_column(2, 2, 20)                # Brand
    worksheet.set_column(3, 3, 15)                # Production #
    worksheet.set_column(4, 4, 30)                # PO Name
    worksheet.set_column(5, 5, 18)                # ETD
    worksheet.set_column(6, 6, 18)                # Arrival Date
    worksheet.set_column(7, 7, 12)                # Fit
    worksheet.set_column(8, 8, 12)                # Fabric Code
    worksheet.set_column(9, 9, 35)                # Fabrication
    worksheet.set_column(10, 10, 12)              # Ship Units
    
    # Row height
    worksheet.set_default_row(112.5)
    
    print(f"Downloading images for {len(data)} items...")
    
    # Download images - now trying multiple formats
    tasks = [(idx, get_image_url(item, s3_base_url)) for idx, item in enumerate(data)]
    processed_images = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_idx = {
            executor.submit(try_multiple_image_urls, urls, TARGET_W, TARGET_H): idx 
            for idx, urls in tasks
        }
        
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                if result:
                    processed_images[idx] = result
                    print(f"✓ Image {idx+1}/{len(data)}")
            except Exception:
                pass
    
    print(f"Downloaded {len(processed_images)}/{len(data)} images")
    
    # Write data
    for row_num, item in enumerate(data):
        excel_row = row_num + 1
        is_even = (row_num % 2 == 1)
        
        current_fmt = fmt_cell_even if is_even else fmt_cell_odd
        
        data_values = [
            '',  # Image placeholder
            item.get('sku', ''),
            item.get('brand_full', ''),
            item.get('production', ''),
            item.get('po_name', ''),
            item.get('etd', ''),
            item.get('arrival', ''),
            item.get('fit', 'N/A'),
            item.get('fabric_code', 'N/A'),
            item.get('fabrication', 'Standard Fabric'),
            item.get('total_warehouse', 0)  # Using as Ship Units
        ]
        
        for col_num, value in enumerate(data_values):
            # Use number format for Ship Units column (10)
            if col_num == 10:
                fmt_to_use = fmt_number_even if is_even else fmt_number_odd
            else:
                fmt_to_use = current_fmt
            
            worksheet.write(excel_row, col_num, value, fmt_to_use)
        
        img_data = processed_images.get(row_num)
        
        if img_data:
            try:
                worksheet.insert_image(excel_row, 0, "img.png", {
                    'image_data': img_data['image_data'],
                    'x_scale': img_data['x_scale'],
                    'y_scale': img_data['y_scale'],
                    'x_offset': img_data['x_offset'],
                    'y_offset': img_data['y_offset'],
                    'object_position': 1,
                    'url': img_data['url']
                })
            except:
                worksheet.write(excel_row, 0, "Error", current_fmt)
        else:
            worksheet.write(excel_row, 0, "No Image", current_fmt)
    
    # Add size scale charts at bottom - GRID FORMAT SIDE BY SIDE
    # Add one blank row gap before the charts start
    chart_start_row = len(data) + 2
    
    # Title format (black text, white background)
    fmt_title = workbook.add_format({
        'bold': True,
        'font_name': STYLE_CONFIG['font_name'],
        'font_size': 11,
        'bg_color': '#FFFFFF',
        'font_color': '#000000',
        'border': 0,
        'align': 'left',
        'valign': 'vcenter'
    })
    
    # Subtitle format (red text)
    fmt_subtitle = workbook.add_format({
        'bold': True,
        'font_name': STYLE_CONFIG['font_name'],
        'font_size': 10,
        'bg_color': '#FFFFFF',
        'font_color': '#FF0000',
        'border': 0,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    # Grid header format (column headers in grid)
    fmt_grid_header = workbook.add_format({
        'bold': True,
        'font_name': STYLE_CONFIG['font_name'],
        'font_size': 10,
        'border': 1,
        'border_color': '#000000',
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#FFFFFF'
    })
    
    # Grid data format
    fmt_grid_data = workbook.add_format({
        'font_name': STYLE_CONFIG['font_name'],
        'font_size': 10,
        'border': 1,
        'border_color': '#000000',
        'align': 'center',
        'valign': 'vcenter',
        'bg_color': '#FFFFFF'
    })
    
    # Set condensed row heights for the chart area
    worksheet.set_row(chart_start_row, 20)      # Title row
    worksheet.set_row(chart_start_row + 1, 18)  # Subtitle row
    worksheet.set_row(chart_start_row + 2, 25)  # Header row
    worksheet.set_row(chart_start_row + 3, 25)  # Data row 1
    worksheet.set_row(chart_start_row + 4, 25)  # Data row 2
    
    # SLIM FIT - Left side (columns 0-5)
    # Title
    worksheet.write(chart_start_row, 0, 'Slim Fit 9 pcs inner, 36 pcs / box (4 inners)', fmt_title)
    
    # Subtitle
    worksheet.merge_range(chart_start_row + 1, 0, chart_start_row + 1, 4,
                          '9 PC. Slim Fit SIZE SCALE TO USE', fmt_subtitle)
    
    # Grid headers
    worksheet.write(chart_start_row + 2, 0, '', fmt_grid_header)  # Top-left corner
    worksheet.write(chart_start_row + 2, 1, '14-14.5', fmt_grid_header)
    worksheet.write(chart_start_row + 2, 2, '15-15.5', fmt_grid_header)
    worksheet.write(chart_start_row + 2, 3, '16-16.5', fmt_grid_header)
    worksheet.write(chart_start_row + 2, 4, '17-17.5', fmt_grid_header)
    
    # Row 1: 32/33
    worksheet.write(chart_start_row + 3, 0, '32/33', fmt_grid_header)
    worksheet.write(chart_start_row + 3, 1, 1, fmt_grid_data)
    worksheet.write(chart_start_row + 3, 2, 2, fmt_grid_data)
    worksheet.write(chart_start_row + 3, 3, 1, fmt_grid_data)
    worksheet.write(chart_start_row + 3, 4, '', fmt_grid_data)
    
    # Row 2: 34/35
    worksheet.write(chart_start_row + 4, 0, '34/35', fmt_grid_header)
    worksheet.write(chart_start_row + 4, 1, '', fmt_grid_data)
    worksheet.write(chart_start_row + 4, 2, 1, fmt_grid_data)
    worksheet.write(chart_start_row + 4, 3, 2, fmt_grid_data)
    worksheet.write(chart_start_row + 4, 4, 2, fmt_grid_data)
    
    # REGULAR FIT - Right side (columns 7-12)
    # Title
    worksheet.write(chart_start_row, 7, 'Regular Fit 9 pcs inner, 36 pcs / box (4 inners)', fmt_title)
    
    # Subtitle
    worksheet.merge_range(chart_start_row + 1, 7, chart_start_row + 1, 11,
                          '9 PC. CLASSIC FIT & REGULAR FIT SIZE SCALE TO USE', fmt_subtitle)
    
    # Grid headers
    worksheet.write(chart_start_row + 2, 7, '', fmt_grid_header)  # Top-left corner
    worksheet.write(chart_start_row + 2, 8, '15-15.5', fmt_grid_header)
    worksheet.write(chart_start_row + 2, 9, '16-16.5', fmt_grid_header)
    worksheet.write(chart_start_row + 2, 10, '17-17.5', fmt_grid_header)
    worksheet.write(chart_start_row + 2, 11, '18-18.5', fmt_grid_header)
    
    # Row 1: 32/33
    worksheet.write(chart_start_row + 3, 7, '32/33', fmt_grid_header)
    worksheet.write(chart_start_row + 3, 8, 1, fmt_grid_data)
    worksheet.write(chart_start_row + 3, 9, 2, fmt_grid_data)
    worksheet.write(chart_start_row + 3, 10, 1, fmt_grid_data)
    worksheet.write(chart_start_row + 3, 11, '', fmt_grid_data)
    
    # Row 2: 34/35
    worksheet.write(chart_start_row + 4, 7, '34/35', fmt_grid_header)
    worksheet.write(chart_start_row + 4, 8, '', fmt_grid_data)
    worksheet.write(chart_start_row + 4, 9, 1, fmt_grid_data)
    worksheet.write(chart_start_row + 4, 10, 2, fmt_grid_data)
    worksheet.write(chart_start_row + 4, 11, 2, fmt_grid_data)
    
    workbook.close()
    output.seek(0)
    
    return output

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "Versa Inventory Export API"})

@app.route('/export', methods=['POST'])
def export_excel():
    try:
        req_data = request.get_json()
        
        if not req_data or 'data' not in req_data:
            return jsonify({"error": "Missing 'data' in request body"}), 400
        
        data = req_data['data']
        s3_base_url = req_data.get('s3_base_url', '')
        filename = req_data.get('filename', 'Inventory_Export')
        
        if not s3_base_url:
            return jsonify({"error": "Missing 's3_base_url' in request body"}), 400
        
        if not data:
            return jsonify({"error": "Data array is empty"}), 400
        
        timestamp = datetime.now().strftime('%Y-%m-%d')
        excel_filename = f"{filename}_{timestamp}.xlsx"
        
        print(f"\n{'='*60}")
        print(f"Creating Excel: {excel_filename}")
        print(f"Items: {len(data)}")
        print(f"{'='*60}\n")
        
        excel_file = create_excel_with_images(data, s3_base_url, filename)
        
        print(f"\n✅ Excel file created!\n")
        
        return send_file(
            excel_file,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=excel_filename
        )
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"\n❌ ERROR:\n{error_trace}\n")
        return jsonify({"error": str(e), "trace": error_trace}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    
    print("="*70)
    print(" 🚀 VERSA INVENTORY EXPORT API")
    print("="*70)
    print(" EMPLOYEE'S EXACT CODE")
    print("="*70)
    print(f"\n📍 Server: http://0.0.0.0:{port}")
    print("📊 Endpoints:")
    print("   GET  /health  - Health check")
    print("   POST /export  - Generate Excel with images")
    print("\n" + "="*70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=True)
