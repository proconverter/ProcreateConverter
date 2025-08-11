import os
import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# --- Configuration ---
ETSY_API_KEY = os.environ.get('ETSY_API_KEY')
ETSY_SHOP_ID = "PresentAndCherish"
MAX_FILE_SIZE = 50 * 1024 * 1024 # 50 MB in bytes

@app.route('/', methods=['GET', 'POST'])
def home():
    message = "" 

    if request.method == 'POST':
        order_id = request.form.get('order_id')
        uploaded_file = request.files.get('brush_file')

        # --- 1. FILE VALIDATION (NEW SECTION) ---
        if not uploaded_file:
            message = "Error: No file was uploaded. Please select a .brushset file."
            return render_template('index.html', message=message)

        if not uploaded_file.filename.lower().endswith('.brushset'):
            message = "Error: Invalid file type. Please upload a .brushset file."
            return render_template('index.html', message=message)
        
        # Check file size (by reading the file into memory - careful with large files)
        # A better way for huge files exists, but this is fine for our limit.
        uploaded_file.seek(0, os.SEEK_END)
        file_length = uploaded_file.tell()
        uploaded_file.seek(0) # Reset file pointer
        if file_length > MAX_FILE_SIZE:
            message = "Error: File is too large. Maximum size is 50 MB."
            return render_template('index.html', message=message)

        # --- 2. ETSY API VALIDATION (Only runs if file is OK) ---
        if not ETSY_API_KEY or not ETSY_SHOP_ID:
            message = "Error: The application is not configured correctly."
            return render_template('index.html', message=message)

        api_url = f"https://openapi.etsy.com/v3/application/shops/{ETSY_SHOP_ID}/receipts/{order_id}"
        headers = {'x-api-key': ETSY_API_KEY}

        try:
            response = requests.get(api_url, headers=headers )
            
            if response.status_code == 200:
                # Both file and Order ID are valid!
                message = f"Success! Order ID {order_id} is valid. File is valid. Ready for conversion!"
            elif response.status_code == 404:
                message = f"Error: Order ID {order_id} not found. Please check the number and try again."
            else:
                message = f"Error: Could not verify order. Status code: {response.status_code}. (Note: Key may be pending activation)."

        except Exception as e:
            message = f"An error occurred: {e}"

    return render_template('index.html', message=message)
