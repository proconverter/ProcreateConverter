import os
import requests
import zipfile
import shutil
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PIL import Image # The new library we are using

app = Flask(__name__)

# --- Configuration ---
ETSY_API_KEY = os.environ.get('ETSY_API_KEY')
ETSY_SHOP_ID = "PresentAndCherish"
MAX_FILE_SIZE = 50 * 1024 * 1024 # 50 MB
MAX_BRUSH_COUNT = 100
# Create folders to store temporary files
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
            # Check for too many brushes
            if len(brushset_zip.namelist()) > MAX_BRUSH_COUNT * 2: # *2 to be safe for shape/grain
                shutil.rmtree(temp_extract_dir)
                return None, "Error: Brush set contains more than 100 brushes."

            # Extract all files
            brushset_zip.extractall(temp_extract_dir)

            # Find the actual image files (they don't have extensions)
            for root, dirs, files in os.walk(temp_extract_dir):
                for name in files:
                    try:
                        # Try to open the file as an image to verify it
                        img_path = os.path.join(root, name)
                        with Image.open(img_path) as img:
                            # It's a valid image, let's keep it
                            extracted_images.append(img_path)
                    except IOError:
                        # This file is not an image, ignore it
                        continue
        
        if not extracted_images:
            shutil.rmtree(temp_extract_dir)
            return None, "Error: No valid images found in the .brushset file."

        # Create a new ZIP file for the output
        output_zip_filename = os.path.basename(filepath).replace('.brushset', '.zip')
        output_zip_path = os.path.join(OUTPUT_FOLDER, output_zip_filename)

        with zipfile.ZipFile(output_zip_path, 'w') as output_zip:
            for i, img_path in enumerate(extracted_images):
                # Rename the file to have a .png extension inside the zip
                output_zip.write(img_path, f'brush_{i+1}.png')

        # Clean up the temporary extraction folder
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
        # (File validation code is the same as before...)
        order_id = request.form.get('order_id')
        uploaded_file = request.files.get('brush_file')

        if not uploaded_file or not uploaded_file.filename:
            message = "Error: No file was uploaded."
            return render_template('index.html', message=message)
        if not uploaded_file.filename.lower().endswith('.brushset'):
            message = "Error: Invalid file type. Please upload a .brushset file."
            return render_template('index.html', message=message)
        
        # (Etsy API validation is the same as before...)
        # For now, we will comment this out so we can test the conversion without a valid key
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

        # Call our new conversion function
        output_path, error_message = process_brushset(filepath)

        # Clean up the uploaded file
        os.remove(filepath)

        if error_message:
            return render_template('index.html', message=error_message)
        
        if output_path:
            # Success! Send the generated ZIP file to the user for download.
            return send_file(output_path, as_attachment=True)

    return render_template('index.html', message=message)

