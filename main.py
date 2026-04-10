import os
import shutil
from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import Request
from fastapi.responses import HTMLResponse
import models
from database import engine, SessionLocal
from models import Product, Category
import easyocr
import re
from models import Order
from datetime import timedelta
from starlette.middleware.sessions import SessionMiddleware
from fastapi import HTTPException
from jwt_auth import create_token
from fastapi import Depends  # เพิ่ม Depends ถ้ายังไม่มี
from jwt_auth import verify_token # ดึงฟังก์ชัน verify_token เข้ามาใช้งาน



# 1. ต้องประกาศสร้าง app ขึ้นมาก่อน
app = FastAPI()

# 2. จากนั้นถึงจะเอา app มาแอด middleware ได้
app.add_middleware(SessionMiddleware, secret_key="secret123")

# ลำดับที่ 3: ค่อยตั้งค่าอื่นๆ เช่น Database, Static files, Templates
models.Base.metadata.create_all(bind=engine)





app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "static/uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "message": "Welcome to My Web App",
        "username": "Somchai",
        "email": "somchai@mail.com",
        "score": 95,
        "activities": ["Running", "Go", "Football"]
    })

# --- แสดงรายการสินค้า (Read) ---
@app.get("/products", response_class=HTMLResponse)
def product_list(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return templates.TemplateResponse("product_list.html", {
        "request": request,
        "products": products
    })

# --- เพิ่มสินค้า (Create) ---
@app.get("/products/create", response_class=HTMLResponse)
def create_form(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    return templates.TemplateResponse("product_form.html", {
        "request": request,
        "categories": categories
    })

@app.post("/products/create")
def create_product(
    name: str = Form(...),
    price: float = Form(...),
    category_id: int = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    filename = None
    if image and image.filename:
        filename = image.filename
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    product = Product(name=name, price=price, category_id=category_id, image=filename)
    db.add(product)
    db.commit()

    return RedirectResponse("/products", status_code=303)

# --- แก้ไขสินค้า (Update) ---
@app.get("/products/edit/{id}", response_class=HTMLResponse)
def edit_form(request: Request, id: int, db: Session = Depends(get_db)):
    product = db.get(Product, id)
    categories = db.query(Category).all()
    return templates.TemplateResponse("product_form.html", {
        "request": request,
        "product": product,
        "categories": categories
    })

@app.post("/products/edit/{id}")
def update_product(
    id: int,
    name: str = Form(...),
    price: float = Form(...),
    category_id: int = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    product = db.get(Product, id)

    # ถ้าหาสินค้าไม่เจอ ให้กลับไปหน้า /products
    if not product:
        return RedirectResponse("/products", status_code=303)

    product.name = name
    product.price = price
    product.category_id = category_id

    # อัปเดตรูปภาพเฉพาะเมื่อมีการแนบไฟล์ใหม่มา
    if image and image.filename:
        filename = image.filename
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        product.image = filename

    db.commit()
    return RedirectResponse("/products", status_code=303)

# --- ลบสินค้า (Delete) ---
@app.get("/products/delete/{id}")
def delete_product(id: int, db: Session = Depends(get_db)):
    product = db.get(Product, id)
    if product:
        db.delete(product)
        db.commit()

    return RedirectResponse("/products", status_code=303)



# Line 153
@app.get("/api/servertime")
def get_datetime():
    return {
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/products/search", response_class=HTMLResponse)
def product_search(request: Request):
    return templates.TemplateResponse("product_search.html", {
        "request": request,
    })


@app.get("/api/products/search")
def product_search_api(search: str = ""):
    db = SessionLocal()
    try:

        return db.query(Product).filter(
            Product.name.like(f"%{search}%")
        ).all()
    finally:
        db.close()




reader = easyocr.Reader(['th', 'en'])

@app.get("/pvs/upload", response_class=HTMLResponse)
def pvs_upload(request: Request):
    return templates.TemplateResponse("pvs_upload.html", {
        "request": request,
    })

@app.post("/api/pvs/upload-ocr")
async def upload_ocr(file: UploadFile = File(...)):

    filepath = os.path.join(UPLOAD_DIR, file.filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)


    result = process_ocr(filepath)
    return result

def process_ocr(image_path):

    result = reader.readtext(image_path)
    text = " ".join([r[1] for r in result])


    amount_match = re.search(r'\d+\.\d{2}', text)
    amount = float(amount_match.group()) if amount_match else 0


    date_match = parse_thai_datetime(text)

    return {
        "text": text,
        "amount": amount,
        "datetime": date_match,
    }

def parse_thai_datetime(text):
    thai_months = {
        "ม.ค.": 1, "ก.พ.": 2, "มี.ค.": 3,
        "เม.ย.": 4, "พ.ค.": 5, "มิ.ย.": 6,
        "ก.ค.": 7, "ส.ค.": 8, "ก.ย.": 9,
        "ต.ค.": 10, "พ.ย.": 11, "ธ.ค.": 12
    }

    match = re.search(
        r'(\d{1,2})\s+([^\s]+)\s+(\d{2})(?:.*?(\d{1,2}):(\d{2}))?',
        text
    )

    if not match:
        return None

    day = int(match.group(1))
    month = thai_months.get(match.group(2), 1)
    year_ad = int(match.group(3)) + 2500 - 543

    time_match = re.search(r'(\d{1,2}):(\d{2})', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    else:
        hour = 0
        minute = 0

    return datetime(year_ad, month, day, hour, minute)


@app.get("/api/pvs/orders")
def get_orders():
    db = SessionLocal()
    try:
        orders = db.query(Order).all()
        return [
            {
                "id": o.id,
                "order_no": o.order_no,
                "amount_total": o.amount_total,
                "order_date": str(o.order_date),
                "state": o.state
            }
            for o in orders
        ]
    finally:
        db.close()


@app.post("/api/pvs/verify-slip")
async def verify_slip(data: dict):
    amount = data["amount"]
    paid_at = datetime.strptime(data["datetime"], "%Y-%m-%dT%H:%M:%S")
    start = paid_at - timedelta(minutes=10)
    end = paid_at + timedelta(minutes=10)

    db = SessionLocal()
    try:
        orders = db.query(Order).filter(
            Order.amount_total == amount,
            Order.order_date >= start,
            Order.order_date <= end,
            Order.state == "Draft"
        ).all()

        return [
            {
                "id": o.id,
                "order_no": o.order_no,
                "amount_total": o.amount_total,
                "order_date": str(o.order_date)
            }
            for o in orders
        ]
    finally:
        db.close()

# API สำหรับเปลี่ยนสถานะออเดอร์เป็น "Paid"
@app.post("/api/pvs/mark-paid")
def mark_paid(data: dict):
    order_ids = data.get("order_ids", [])
    db = SessionLocal()
    try:
        orders = db.query(Order).filter(Order.id.in_(order_ids)).all()
        for o in orders:
            o.state = "Paid"
        db.commit()
        return {"status": "success"}
    finally:
        db.close()

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {
        "request": request
    })


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str =
Form(...)):
     if username == "admin" and password == "1234":
        request.session["user"] = username
        return RedirectResponse("/", status_code=303)
     return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Login failed"
    })

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# นำมาเขียนไว้ด้านล่างสุดที่เดียวเลยครับ
def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=303)
    return user

@app.get("/", response_class=HTMLResponse)
def home(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user

    # รวมโค้ดแสดงผลหน้า Home มาไว้ตรงนี้
    return templates.TemplateResponse("index.html", {
        "request": request,
        "message": "Welcome to My Web App",
        "username": user, # ดึงชื่อ user จากคนที่ล็อกอินเข้ามาแสดงได้เลย
        "email": "somchai@mail.com",
        "score": 95,
        "activities": ["Running", "Go", "Football"]
    })

@app.post("/api/login")
def api_login(username: str, password: str):
    if username == "admin" and password == "1234":
        token = create_token(username)
        return {
            "access_token": token,
            "token_type": "bearer"
        }
    raise HTTPException(
        status_code=401,
        detail="Invalid username or password"
    )

# เพิ่มไว้ด้านล่างสุดของ main.py
@app.get("/api/v1/users")
def user_list(user = Depends(verify_token)): # ตัว Depends จะบังคับให้ต้องเช็ค Token ก่อน
    return {
        "message": "List of users",
        "current_user": user # คืนค่าข้อมูลที่ถอดรหัสได้กลับไปให้ดูด้วย
    }
