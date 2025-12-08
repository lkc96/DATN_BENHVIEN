import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # 1. Lấy URL từ biến môi trường
    database_url = os.getenv('DATABASE_URL')

    # 2. FIX LỖI QUAN TRỌNG TRÊN RENDER:
    # Render thường trả về "postgres://...", nhưng SQLAlchemy yêu cầu "postgresql://..."
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # 3. Nếu không tìm thấy biến môi trường (tức là đang chạy ở máy nhà)
    # thì mới dùng localhost
    if not database_url:
        # Chuỗi kết nối máy Local của bạn
        database_url = 'postgresql://postgres:1410434@localhost:5432/DATN_Benhvien'

    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY', '1410434lkc')