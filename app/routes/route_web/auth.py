
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import Account

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Nếu đã login rồi thì chuyển vào trong luôn
    if current_user.is_authenticated:
        return redirect(url_for('main.index')) # Hoặc trang dashboard

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = Account.query.filter_by(username=username).first()

        # 1. Kiểm tra User tồn tại và Mật khẩu đúng
        if not user or not user.check_password(password):
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'danger')
            return render_template('auth/login.html')

        # 2. [QUAN TRỌNG] KIỂM TRA QUYỀN TRUY CẬP HỆ THỐNG
        # Logic: Chỉ cho phép STAFF đăng nhập, chặn PATIENT
        # (Dựa vào quan hệ 1-1: user.staff sẽ có dữ liệu, user.patient sẽ None hoặc ta không quan tâm)
        
        if not user.staff: 
            flash('Tài khoản này không có quyền truy cập hệ thống quản lý.', 'warning')
            return render_template('auth/login.html')

        # 3. Đăng nhập thành công
        login_user(user, remember=remember)
        
        # Lấy tham số 'next' để chuyển hướng lại trang người dùng đang muốn vào
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.index')) # Sửa main_bp.index theo tên route dashboard của bạn

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth_bp.login'))