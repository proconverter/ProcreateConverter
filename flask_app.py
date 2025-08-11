import os
import requests
import zipfile
import shutil
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)

# --- Configuration ---
ETSY_API_KEY = os.environ.get('ETSY_API_KEY')
ETSY_SHOP_ID = "PresentAndCherish"
MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_BRUSH_COUNT = 100
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- Helper Function: The Conversion Engine ---
def process_brushset(filepath):
    temp_extract_dir = os.path.join(UPLOAD_FOLDER, 'temp_extract')
    os.makedirs(temp_extract_dir, exist_ok=True)
    
    extracted_images = []
    try:
        with zipfile.ZipFile(filepath, 'r') as brushset_zip:
            if len(brushset_zip.namelist()) > MAX_BRUSH_COUNT * 2:
                shutil.rmtree(temp_extract_dir)
                return None, "Error: Brush set contains more than 100 brushes."

            brushset_zip.extractall(temp_extract_dir)

            for root, dirs, files in os.walk(temp_extract_dir):
                for name in files:
                    try:
                        img_path = os.path.join(root, name)
                        with Image.open(img_path) as img:
                            extracted_images.append(img_path)
                    except IOError:
                        continue
        
        if not extracted_images:
            shutil.rmtree(temp_extract_dir)
            return None, "Error: No valid images found in the .brushset file."

        output_zip_filename = os.path.basename(filepath).replace('.brushset', '.zip')
        output_zip_path = os.path.join(OUTPUT_FOLDER, output_zip_filename)

        with zipfile.ZipFile(output_zip_path, 'w') as output_zip:
            for i, img_path in enumerate(extracted_images):
                output_zip.write(img_path, f'brush_{i+1}.png')

        shutil.rmtree(temp_extract_dir)
        return output_zip_path, None

    except zipfile.BadZipFile:
        shutil.rmtree(temp_extract_dir)
        return None, "Error: The uploaded file is not a valid .brushset (corrupt zip)."
    except Exception as e:
        shutil.rmtree(temp_extract_dir)
        return None, f"An unexpected error occurred: {str(e)}"

@app.route('/', methods=['GET', 'POST'])
def home():
    message = "" 
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        uploaded_file = request.files.get('brush_file')

        # --- 1. FILE VALIDATION (IMPROVED) ---
        if not uploaded_file or not uploaded_file.filename or not uploaded_file.filename.lower().endswith('.brushset'):
            message = "Error: You must upload a valid .brushset file."
            return render_template('index.html', message=message)

        # --- Etsy API Validation (Commented out for testing) ---
        # api_url = f"https://openapi.etsy.com/v3/application/shops/{ETSY_SHOP_ID}/receipts/{order_id}"
        # headers = {'x-api-key': ETSY_API_KEY}
        # response = requests.get(api_url, headers=headers )
        # if response.status_code != 200:
        #     message = f"Error: Could not verify order. Status code: {response.status_code}."
        #     return render_template('index.html', message=message)

        # --- Save the file and start conversion ---
        filename = secure_filename(uploaded_file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        uploaded_file.save(filepath)

        output_path, error_message = process_brushset(filepath)

        os.remove(filepath)

        if error_message:
            return render_template('index.html', message=error_message)
        
        if output_path:
            return send_file(output_path, as_attachment=True)

    return render_template('index.html', message=message)
