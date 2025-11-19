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
templates = Jinja2Templates(directory="../templates")

# KHQR Setup
api_token_bakong = os.getenv("KHQR_API_TOKEN", "YOUR_API_TOKEN")
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

# Payment tracking
payments = {}

def generate_short_transaction_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

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
        print("QR error:", e)
        return None, None

def check_payment(md5, amount, item_name):
    # Vercel cannot run long-running threads for >10s, so polling must be done on frontend
    pass  # We will let frontend call /status repeatedly

@app.get("/", response_class=HTMLResponse)
async def shop(request: Request):
    return templates.TemplateResponse("shop.html", {"request": request, "items": items})

@app.get("/buy/{item_id}", response_class=HTMLResponse)
async def buy(request: Request, item_id: str):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    item = items[item_id]
    qr_code, md5 = generate_qr_code(item["price"])
    if not qr_code:
        return HTMLResponse("Failed to generate QR code", status_code=500)
    payments[md5] = {
        "status": "pending",
        "message": None,
        "qr_code": qr_code,
        "item_name": item["name"],
        "amount": item["price"]
    }
    return templates.TemplateResponse("buy.html", {"request": request, "item": item, "qr_code": qr_code, "md5": md5})

@app.get("/status/{md5}")
async def status(md5: str):
    # Frontend must poll /status for updates
    return JSONResponse(payments.get(md5, {"status": "not_found", "message": "Invalid transaction."}))
