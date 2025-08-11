from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def home():
    message = "" # Start with an empty message
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        message = f"Form submitted! We received Order ID: {order_id}. Backend logic is next."
    
    return render_template('index.html', message=message)
