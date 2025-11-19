from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

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

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# KHQR setup
api_token_bakong = os.getenv("KHQR_API_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7ImlkIjoiY2U3NTMwODdiMjQ5NDQzZSJ9LCJpYXQiOjE3NjE1MzU0MjgsImV4cCI6MTc2OTMxMTQyOH0.e3w8uD5-GEtN_K_tFK0dydN8M0f4bxh_Qj3Y0AMaIzk")
khqr = KHQR(api_token_bakong)
BANK_ACCOUNT = os.getenv("BANK_ACCOUNT", "chhira_ly@aclb")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "855882000544")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Phnom_Penh")

# Items
items = {
    '86': {'name': '86 Diamonds', 'price': 1.18},
    '172': {'name': '172 Diamonds', 'price': 2.35},
    'phone': {'name': 'Smartphone', 'price': 800.0},
    'laptop': {'name': 'Laptop', 'price': 1200.0},
    'book': {'name': 'Book', 'price': 15.0},
    'headphones': {'name': 'Headphones', 'price': 100.0},
    'watch': {'name': 'Smartwatch', 'price': 250.0},
    'tablet': {'name': 'Tablet', 'price': 400.0},
    'camera': {'name': 'Digital Camera', 'price': 600.0},
    'shoes': {'name': 'Running Shoes', 'price': 80.0}
}

# Store payment states
payments = {}

def generate_short_transaction_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Generate QR code with error logging
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
        print("QR generation failed:", e)
        return None, None

# Background payment checker
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
                    timezone = pytz.timezone(TIMEZONE)
                    current_time = datetime.now(timezone).strftime("%d/%m/%Y %H:%M")
                    payments[md5]["status"] = "success"
                    payments[md5]["message"] = f"Thank you for buying {item_name}! Payment of ${amount:.2f} received at {current_time}."
                    return
            except Exception as e:
                print(f"Payment check error: {e}")
            time.sleep(10)
        # Timeout
        payments[md5]["status"] = "failed"
        payments[md5]["message"] = "Payment not received within 3 minutes. Please try again."
        payments[md5]["qr_code"] = None
    threading.Thread(target=poll, daemon=True).start()

# Shop page
@app.get("/", response_class=HTMLResponse)
async def shop(request: Request):
    return templates.TemplateResponse("shop.html", {"request": request, "items": items})

# Buy page
@app.get("/buy/{item_id}", response_class=HTMLResponse)
async def buy(request: Request, item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = items[item_id]
    qr_base64, md5 = generate_qr_code(item['price'])
    if not qr_base64 or not md5:
        return HTMLResponse("Failed to generate QR code. Check server logs.", status_code=500)
    payments[md5] = {
        "status": "pending",
        "message": None,
        "qr_code": qr_base64
    }
    check_payment(md5, item['price'], item['name'])
    return templates.TemplateResponse("buy.html", {"request": request, "item": item, "qr_code": qr_base64, "md5": md5})

# Status endpoint
@app.get("/status/{md5}")
async def status(md5: str):
    return JSONResponse(payments.get(md5, {"status": "not_found", "message": "Invalid transaction."}))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
