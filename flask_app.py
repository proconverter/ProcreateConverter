import os
import requests
from flask import Flask, render_template, request

# This creates the Flask web application
app = Flask(__name__)

# --- Configuration ---
ETSY_API_KEY = os.environ.get('ETSY_API_KEY')
ETSY_SHOP_ID = "PresentAndCherish" # Your actual Shop ID

# This is the main route for your website (the homepage)
@app.route('/', methods=['GET', 'POST'])
def home():
    # ** THE FIX IS HERE: Define message at the start **
    message = "" 

    # This block of code will run when a user submits the form
    if request.method == 'POST':
        order_id = request.form.get('order_id')

        # --- Etsy API Validation Logic ---
        if not ETSY_API_KEY or not ETSY_SHOP_ID:
            message = "Error: The application is not configured correctly. Please contact the site owner."
            return render_template('index.html', message=message)

        api_url = f"https://openapi.etsy.com/v3/application/shops/{ETSY_SHOP_ID}/receipts/{order_id}"
        
        headers = {
            'x-api-key': ETSY_API_KEY
        }

        try:
            response = requests.get(api_url, headers=headers )
            
            if response.status_code == 200:
                message = f"Success! Order ID {order_id} is valid. File processing will happen here."
            elif response.status_code == 404:
                message = f"Error: Order ID {order_id} not found. Please check the number and try again."
            else:
                # This will catch errors like 403 (Forbidden) if the key isn't active yet
                message = f"Error: Could not verify order. Status code: {response.status_code}. Note: If the key is new, it may still be pending activation by Etsy."

        except Exception as e:
            message = f"An error occurred while contacting the server: {e}"

    # Render the page, passing in any message we generated
    return render_template('index.html', message=message)
