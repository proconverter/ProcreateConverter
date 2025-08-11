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
MIN_IMAGE_DIMENSION = 500
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Helper Function: The Final, Memory-Safe Conversion Engine ---
def process_brushset(filepath):
    # Create unique temporary directories for this specific conversion
    base_filename = os.path.basename(filepath)
    temp_extract_dir = os.path.join(UPLOAD_FOLDER, f"extract_{base_filename}")
    temp_output_dir = os.path.join(UPLOAD_FOLDER, f"output_{base_filename}")
    os.makedirs(temp_extract_dir, exist_ok=True)
    os.makedirs(temp_output_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(filepath, 'r') as brushset_zip:
            if len(brushset_zip.namelist()) > MAX_BRUSH_COUNT * 2:
                return None, "Error: Brush set contains more than 100 brushes."

            brushset_zip.extractall(temp_extract_dir)

            final_image_paths = []
            for root, dirs, files in os.walk(temp_extract_dir):
                for name in files:
                    try:
                        img_path = os.path.join(root, name)
                        with Image.open(img_path) as img:
                            width, height = img.size
                            if width >= MIN_IMAGE_DIMENSION and height >= MIN_IMAGE_DIMENSION:
                                final_image = img
                                if img.mode == 'L':
                                    transparent_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                    transparent_img.putalpha(img)
                                    final_image = transparent_img
                                
                                # Save the final transparent image to our temporary output folder
                                output_image_path = os.path.join(temp_output_dir, name)
                                final_image.save(output_image_path, 'PNG')
                                final_image_paths.append(output_image_path)
                    except IOError:
                        continue

        if not final_image_paths:
            return None, "Error: No valid brushes found in the file. (Images might be too small)."

        # Create the output ZIP file from the temporary output folder
        output_zip_path = os.path.join(UPLOAD_FOLDER, base_filename.replace('.brushset', '.zip'))
        with zipfile.ZipFile(output_zip_path, 'w') as output_zip:
            for i, img_path in enumerate(final_image_paths):
                output_zip.write(img_path, f'brush_{i+1}.png')

        return output_zip_path, None

    except zipfile.BadZipFile:
        return None, "Error: The uploaded file is not a valid .brushset (corrupt zip)."
    except Exception as e:
        return None, f"An unexpected error occurred: {str(e)}"
    finally:
        # Clean up all our temporary folders
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)
        if os.path.exists(temp_output_dir):
            shutil.rmtree(temp_output_dir)

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

        output_path, error_message = process_brushset(filepath)

        if os.path.exists(filepath):
            os.remove(filepath)

        if error_message:
            return render_template('index.html', message=error_message)

        if output_path:
            # After sending the file, we should clean it up
            try:
                return send_file(output_path, as_attachment=True)
            finally:
                if os.path.exists(output_path):
                    os.remove(output_path)

        return render_template('index.html', message="An unknown error occurred during processing.")

    return render_template('index.html', message="")
