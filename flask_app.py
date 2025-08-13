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
# NO CHANGES NEEDED IN THIS FUNCTION
def process_brushset(filepath):
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
                                
                                output_image_path = os.path.join(temp_output_dir, name)
                                final_image.save(output_image_path, 'PNG')
                                final_image_paths.append(output_image_path)
                    except IOError:
                        continue

        if not final_image_paths:
            return None, "Error: No valid brushes found in the file (images might be too small)."

        # This function now returns the path to the FOLDER of PNGs
        return temp_output_dir, None

    except zipfile.BadZipFile:
        return None, "Error: The uploaded file is not a valid .brushset (corrupt zip)."
    except Exception as e:
        print(f"Error during brushset processing: {str(e)}")
        return None, "An unexpected error occurred while processing the brush file."
    finally:
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)
        # IMPORTANT: We do NOT clean up the output dir here anymore, it's cleaned up in the main route

# --- Main Application Route (UPDATED FOR MULTI-FILE) ---
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        # --- 1. Etsy API Validation ---
        try:
            order_id = request.form.get('order_id')
            if not order_id or not order_id.strip():
                 return render_template('index.html', message="Error: Please provide a valid Etsy Order ID.")

            # --- This is the block to uncomment when you go live ---
            # api_url = f"https://openapi.etsy.com/v3/application/shops/{ETSY_SHOP_ID}/receipts/{order_id.strip( )}"
            # headers = {'x-api-key': ETSY_API_KEY}
            # response = requests.get(api_url, headers=headers, timeout=10)
            # if response.status_code == 404:
            #     return render_template('index.html', message="Error: This Order ID was not found. Please double-check the number.")
            # elif response.status_code != 200:
            #     print(f"Etsy API Error: Status {response.status_code}, Response: {response.text}")
            #     return render_template('index.html', message="Error: Could not verify the Order ID with Etsy. Please try again later.")

        except requests.exceptions.RequestException as e:
            print(f"Etsy API Request Failed: {e}")
            return render_template('index.html', message="Error: Could not connect to Etsy's servers. Please try again in a few minutes.")

        # --- 2. File Handling and Processing ---
        uploaded_files = request.files.getlist('brush_files') # Use getlist for multiple files

        if not uploaded_files or all(f.filename == '' for f in uploaded_files):
            return render_template('index.html', message="Error: You must upload at least one valid .brushset file.")
        if len(uploaded_files) > 10:
            return render_template('index.html', message="Error: You cannot upload more than 10 files at once.")

        temp_folders_to_clean = []
        temp_files_to_clean = []
        error_messages = []
        processed_data = {} # To store {brushset_name: [png_paths]}

        for uploaded_file in uploaded_files:
            if uploaded_file and uploaded_file.filename.lower().endswith('.brushset'):
                filename = secure_filename(uploaded_file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                
                try:
                    uploaded_file.save(filepath)
                    temp_files_to_clean.append(filepath)
                    
                    output_folder, error_message = process_brushset(filepath)
                    
                    if error_message:
                        error_messages.append(f"{filename}: {error_message}")
                    elif output_folder:
                        temp_folders_to_clean.append(output_folder)
                        png_files = [os.path.join(output_folder, f) for f in os.listdir(output_folder) if f.endswith('.png')]
                        processed_data[filename.replace('.brushset', '')] = png_files
                except Exception as e:
                    print(f"Error saving or processing {filename}: {e}")
                    error_messages.append(f"{filename}: A server error occurred.")
            else:
                error_messages.append(f"{uploaded_file.filename or 'Unknown file'}: Invalid file type.")

        if error_messages:
            # Cleanup before returning error
            for path in temp_files_to_clean: shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
            for path in temp_folders_to_clean: shutil.rmtree(path, ignore_errors=True)
            return render_template('index.html', message="; ".join(error_messages))

        if not processed_data:
            return render_template('index.html', message="Error: No valid brushes could be processed.")

        # --- 3. Combine all PNGs into a single final ZIP file ---
        final_zip_filename = f"Converted_Brushes_{order_id}.zip"
        final_zip_path = os.path.join(UPLOAD_FOLDER, final_zip_filename)

        try:
            with zipfile.ZipFile(final_zip_path, 'w') as final_zip:
                for brushset_name, png_paths in processed_data.items():
                    for i, png_path in enumerate(png_paths):
                        # Create a clean filename inside the zip
                        arcname = os.path.join(brushset_name, f"brush_{i+1}.png")
                        final_zip.write(png_path, arcname)
            
            return send_file(final_zip_path, as_attachment=True)

        except Exception as e:
            print(f"Error creating final zip: {e}")
            return render_template('index.html', message="Error creating the final combined zip file.")
        
        finally:
            # --- 4. Final Cleanup ---
            for path in temp_files_to_clean:
                if os.path.exists(path): os.remove(path)
            for path in temp_folders_to_clean:
                if os.path.exists(path): shutil.rmtree(path, ignore_errors=True)
            if os.path.exists(final_zip_path):
                os.remove(final_zip_path)

    return render_template('index.html', message="")
