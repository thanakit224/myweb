import jwt
from datetime import datetime, timedelta


SECRET_KEY = "secret1234"
ALGORITHM = "HS256"


def create_token(username: str):

    expire = datetime.utcnow() + timedelta(minutes=30)


    payload = {
        "sub": username,
        "exp": expire
    }


    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

# ใส่โค้ดนี้ต่อท้ายในไฟล์ jwt_auth.py
def verify_token(token: str):
    # นำ token มาถอดรหัสด้วย SECRET_KEY ที่เราตั้งไว้
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload
