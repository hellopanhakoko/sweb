from flask import Flask, render_template, request, jsonify, session
import qrcode
import os
import random
import string
import time
import threading
import requests
import pytz
from datetime import datetime
from bakong_khqr import KHQR
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure key

# Bakong KHQR setup (same as before)
api_token_bakong = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiY2U3NTMwODdiMjQ5NDQzZSJ9LCJpYXQiOjE3NjE1MzU0MjgsImV4cCI6MTc2OTMxMTQyOH0.e3w8uD5-GEtN_K_tFK0dydN8M0f4bxh_Qj3Y0AMaIzk"
khqr = KHQR(api_token_bakong)
BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "chhira_ly@aclb")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "855882000544")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Phnom_Penh")

# List of 10 items with various prices
items = {
    '86': {'name': '86 Diamonds', 'price': 1.18},
    '172': {'name': '172  Diamonds', 'price': 2.35},
    'phone': {'name': 'Smartphone', 'price': 800.0},
    'laptop': {'name': 'Laptop', 'price': 1200.0},
    'book': {'name': 'Book', 'price': 15.0},
    'headphones': {'name': 'Headphones', 'price': 100.0},
    'watch': {'name': 'Smartwatch', 'price': 250.0},
    'tablet': {'name': 'Tablet', 'price': 400.0},
    'camera': {'name': 'Digital Camera', 'price': 600.0},
    'shoes': {'name': 'Running Shoes', 'price': 80.0}
}

# Generate short transaction ID
def generate_short_transaction_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Generate QR code and return base64 encoded image
def generate_qr_code(amount):
    try:
        qr_string = khqr.create_qr(
            bank_account=BANK_ACCOUNT,
            merchant_name='PI YA LEGEND',
            merchant_city='Phnom Penh',
            amount=amount,
            currency='USD',
            store_label='MShop',
            phone_number=PHONE_NUMBER,
            bill_number=generate_short_transaction_id(),
            terminal_label='Cashier-01',
            static=False
        )
        qr_img = qrcode.make(qr_string)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        md5 = khqr.generate_md5(qr_string)
        return qr_base64, md5
    except Exception as e:
        print(f"Error generating QR: {e}")
        return None, None

# Check payment status
def check_payment(md5, amount, item_name):
    def poll():
        start_time = time.time()
        while time.time() - start_time < 180:  # 3 minutes
            try:
                url = f"https://panha-dev.vercel.app/check_payment/{md5}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                if data.get("success") and data.get("status") == "PAID":
                    # Payment successful
                    timezone = pytz.timezone(TIMEZONE)
                    current_time = datetime.now(timezone).strftime("%d/%m/%Y %H:%M")
                    session['payment_status'] = 'success'
                    session['message'] = f"Thank you for buying the {item_name}! Payment of ${amount:.2f} received at {current_time}."
                    break
            except Exception as e:
                print(f"Payment check error: {e}")
            time.sleep(10)
        else:
            session['payment_status'] = 'failed'
            session['message'] = "Payment not received within 3 minutes. Please try again."
            session.pop('qr_code', None)  # Remove QR code from session on timeout
    threading.Thread(target=poll).start()

@app.route('/')
def shop():
    return render_template('shop.html', items=items)

@app.route('/buy/<item_id>')
def buy(item_id):
    if item_id not in items:
        return "Item not found", 404
    item = items[item_id]
    qr_base64, md5 = generate_qr_code(item['price'])
    if not qr_base64 or not md5:
        return "Failed to generate QR code. Try again.", 500
    session['qr_code'] = qr_base64
    session['payment_status'] = 'pending'
    session['message'] = None
    check_payment(md5, item['price'], item['name'])
    return render_template('buy.html', item=item, qr_code=qr_base64)

@app.route('/status')
def status():
    return jsonify({
        'status': session.get('payment_status', 'pending'),
        'message': session.get('message')
    })

if __name__ == '__main__':
    app.run(debug=True)
