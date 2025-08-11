import os
import requests
from flask import Flask, render_template, request

# This creates the Flask web application
app = Flask(__name__)

# --- Configuration ---
# Read the secret API key from the environment variables we set on Render
ETSY_API_KEY = os.environ.get('ETSY_API_KEY')
# Your Etsy Shop ID. You can find this in the URL of your Etsy shop page.
# It's the number at the end, e.g., https://www.etsy.com/shop/YourShopName -> 12345678
# For now, we will leave it as a placeholder.
ETSY_SHOP_ID = "YOUR_SHOP_ID_HERE" 


# This is the main route for your website (the homepage )
@app.route('/', methods=['GET', 'POST'])
def home():
    message = "" # Start with an empty message

    # This block of code will run when a user submits the form
    if request.method == 'POST':
        order_id = request.form.get('order_id')

        # --- Etsy API Validation Logic ---
        if not ETSY_API_KEY or ETSY_SHOP_ID == "YOUR_SHOP_ID_HERE":
            message = "Error: The application is not configured correctly. Please contact the site owner."
            return render_template('index.html', message=message)

        # Construct the URL for the Etsy API endpoint
        # This asks for the receipt (order) associated with your shop
        api_url = f"https://openapi.etsy.com/v3/application/shops/{ETSY_SHOP_ID}/receipts/{order_id}"
        
        # Set up the headers for the API request, including our secret key
        headers = {
            'x-api-key': ETSY_API_KEY
        }

        try:
            # Make the actual request to the Etsy API
            response = requests.get(api_url, headers=headers )
            
            # Check if the request was successful (HTTP status code 200)
            if response.status_code == 200:
                # The Order ID is valid and belongs to your shop!
                # For now, we just show a success message.
                # Later, we will add the file conversion logic here.
                message = f"Success! Order ID {order_id} is valid. File processing will happen here."
            elif response.status_code == 404:
                # The Order ID was not found for your shop.
                message = f"Error: Order ID {order_id} not found. Please check the number and try again."
            else:
                # Another error occurred (e.g., Etsy's servers are down)
                message = f"Error: Could not verify order. Status code: {response.status_code}"

        except Exception as e:
            # A network error or other problem happened
            message = f"An error occurred: {e}"

    # Render the page, passing in any message we generated
    return render_template('index.html', message=message)

