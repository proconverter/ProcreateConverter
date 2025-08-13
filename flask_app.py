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
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Helper Function (REVISED) ---
def process_brushset(filepath, make_transparent=False):
    base_filename = os.path.basename(filepath)
    temp_extract_dir = os.path.join(UPLOAD_FOLDER, f"extract_{base_filename}")
    temp_output_dir = os.path.join(UPLOAD_FOLDER, f"output_{base_filename}")
    os.makedirs(temp_extract_dir, exist_ok=True)
    os.makedirs(temp_output_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(filepath, 'r') as brushset_zip:
            brushset_zip.extractall(temp_extract_dir)

            final_image_paths = []
            for root, dirs, files in os.walk(temp_extract_dir):
                for name in files:
                    img_path = os.path.join(root, name)
                    try:
                        with Image.open(img_path) as img:
                            width, height = img.size
                            
                            # Filter for images larger than 1024x1024
                            if width >= 1024 and height >= 1024:
                                final_image = img
                                
                                if make_transparent and img.mode == 'L':
                                    transparent_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
                                    transparent_img.putalpha(img)
                                    final_image = transparent_img
                                
                                output_image_path = os.path.join(temp_output_dir, f"stamp_{name}.png")
                                final_image.save(output_image_path, 'PNG')
                                final_image_paths.append(output_image_path)

                    except (IOError, SyntaxError):
                        # This is expected for non-image files. Ignore and continue.
                        continue

        if not final_image_paths:
            return None, "Error: No valid brushes larger than 1024x1024 were found."

        return temp_output_dir, None

    except zipfile.BadZipFile:
        return None, "Error: The uploaded file is not a valid .brushset (corrupt zip)."
    except Exception as e:
        print(f"Error during brushset processing: {str(e)}")
        return None, "An unexpected error occurred while processing the brush file."
    finally:
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)

# --- Main Application Route ---
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        make_transparent = request.form.get('make_transparent') == 'true'
        uploaded_files = request.files.getlist('brush_files')

        try:
            if not order_id or not order_id.strip():
                 return render_template('index.html', message="Error: Please provide a valid Etsy Order ID.")
            
            # --- Live Etsy API validation block ---
            # api_url = f"https://openapi.etsy.com/v3/application/shops/{ETSY_SHOP_ID}/receipts/{order_id.strip( )}"
            # headers = {'x-api-key': ETSY_API_KEY}
            # response = requests.get(api_url, headers=headers, timeout=10)
            # if response.status_code == 404:
            #     return render_template('index.html', message="Error: This Order ID was not found.")
            # elif response.status_code != 200:
            #     print(f"Etsy API Error: Status {response.status_code}, Response: {response.text}")
            #     return render_template('index.html', message="Error: Could not verify the Order ID with Etsy.")

        except requests.exceptions.RequestException as e:
            print(f"Etsy API Request Failed: {e}")
            return render_template('index.html', message="Error: Could not connect to Etsy's servers.")

        if not uploaded_files or all(f.filename == '' for f in uploaded_files):
            return render_template('index.html', message="Error: You must upload at least one valid .brushset file.")
        if len(uploaded_files) > 10:
            return render_template('index.html', message="Error: You cannot upload more than 10 files at once.")

        temp_folders_to_clean = []
        temp_files_to_clean = []
        error_messages = []
        processed_data = {}
        final_zip_path = ""

        try:
            for uploaded_file in uploaded_files:
                if uploaded_file and uploaded_file.filename.lower().endswith('.brushset'):
                    filename = secure_filename(uploaded_file.filename)
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    
                    uploaded_file.save(filepath)
                    temp_files_to_clean.append(filepath)
                    
                    output_folder, error_message = process_brushset(filepath, make_transparent)
                    
                    if error_message:
                        error_messages.append(f"{filename}: {error_message}")
                    elif output_folder:
                        temp_folders_to_clean.append(output_folder)
                        png_files = [os.path.join(output_folder, f) for f in os.listdir(output_folder) if f.endswith('.png')]
                        processed_data[filename.replace('.brushset', '')] = png_files
                else:
                    error_messages.append(f"{uploaded_file.filename or 'Unknown file'}: Invalid file type.")

            if error_messages:
                error_string = "; ".join(error_messages)
                return render_template('index.html', message=error_string)

            if not processed_data:
                return render_template('index.html', message="Error: No valid brushes could be processed.")

            final_zip_filename = f"Converted_Brushes_{order_id}.zip"
            final_zip_path = os.path.join(UPLOAD_FOLDER, final_zip_filename)

            with zipfile.ZipFile(final_zip_path, 'w') as final_zip:
                for brushset_name, png_paths in processed_data.items():
                    for i, png_path in enumerate(png_paths):
                        arcname = os.path.join(brushset_name, os.path.basename(png_path))
                        final_zip.write(png_path, arcname)
            
            return send_file(final_zip_path, as_attachment=True)

        except Exception as e:
            print(f"Error in main processing block: {e}")
            return render_template('index.html', message="An unexpected server error occurred.")
        
        finally:
            for path in temp_files_to_clean:
                if os.path.exists(path):
                    os.remove(path)
            
            for path in temp_folders_to_clean:
                if os.path.exists(path):
                    shutil.rmtree(path, ignore_errors=True)

            if final_zip_path and os.path.exists(final_zip_path):
                os.remove(final_zip_path)

    return render_template('index.html', message="")
