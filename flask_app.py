import os
import requests
import zipfile
import shutil
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import io # We need this for in-memory file handling

app = Flask(__name__)

# --- Configuration ---
ETSY_API_KEY = os.environ.get('ETSY_API_KEY')
ETSY_SHOP_ID = "PresentAndCherish"
MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_BRUSH_COUNT = 100
MIN_IMAGE_DIMENSION = 500 
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Helper Function: The Final Conversion Engine ---
def process_brushset(filepath):
    temp_extract_dir = os.path.join(UPLOAD_FOLDER, 'temp_extract')
    os.makedirs(temp_extract_dir, exist_ok=True)
    
    try:
        with zipfile.ZipFile(filepath, 'r') as brushset_zip:
            if len(brushset_zip.namelist()) > MAX_BRUSH_COUNT * 2:
                return None, "Error: Brush set contains more than 100 brushes."

            brushset_zip.extractall(temp_extract_dir)
            
            # --- ** THE FIX IS HERE ** ---
            # We will store the final, converted images in a list in memory
            final_images_to_zip = [] 
            
            for root, dirs, files in os.walk(temp_extract_dir):
                for name in files:
                    try:
                        img_path = os.path.join(root, name)
                        with Image.open(img_path) as img:
                            width, height = img.size
                            if width >= MIN_IMAGE_DIMENSION and height >= MIN_IMAGE_DIMENSION:
                                final_image = img
                                # If it's grayscale, convert it to a transparent RGBA image
                                if img.mode == 'L':
                                    transparent_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                    transparent_img.putalpha(img)
                                    final_image = transparent_img
                                
                                # Save the final image (transparent or not) to an in-memory buffer
                                img_buffer = io.BytesIO()
                                final_image.save(img_buffer, format='PNG')
                                img_buffer.seek(0)
                                final_images_to_zip.append(img_buffer)
                    except IOError:
                        continue
        
        if not final_images_to_zip:
            return None, "Error: No valid brushes found in the file. (Images might be too small)."

        # Create the output ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as output_zip:
            for i, img_buffer in enumerate(final_images_to_zip):
                output_zip.writestr(f'brush_{i+1}.png', img_buffer.read())
        
        zip_buffer.seek(0)
        return zip_buffer, None

    except zipfile.BadZipFile:
        return None, "Error: The uploaded file is not a valid .brushset (corrupt zip)."
    except Exception as e:
        return None, f"An unexpected error occurred: {str(e)}"
    finally:
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        uploaded_file = request.files.get('brush_file')

        if not uploaded_file or not uploaded_file.filename or not uploaded_file.filename.lower().endswith('.brushset'):
            return render_template('index.html', message="Error: You must upload a valid .brushset file.")

        # --- Etsy API Validation (Commented out for testing) ---
        # order_id = request.form.get('order_id')
        # api_url = f"https://openapi.etsy.com/v3/application/shops/{ETSY_SHOP_ID}/receipts/{order_id}"
        # headers = {'x-api-key': ETSY_API_KEY}
        # response = requests.get(api_url, headers=headers )
        # if response.status_code != 200:
        #     return render_template('index.html', message=f"Error: Could not verify order. Status code: {response.status_code}.")

        filename = secure_filename(uploaded_file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        uploaded_file.save(filepath)

        zip_buffer, error_message = process_brushset(filepath)

        if os.path.exists(filepath):
            os.remove(filepath)

        if error_message:
            return render_template('index.html', message=error_message)
        
        if zip_buffer:
            zip_filename = filename.replace('.brushset', '.zip')
            return send_file(zip_buffer, as_attachment=True, download_name=zip_filename, mimetype='application/zip')
        
        return render_template('index.html', message="An unknown error occurred during processing.")

    return render_template('index.html', message="")
