
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def role_required(allowed_roles):
    """
    Decorator để kiểm tra quyền truy cập.
    :param allowed_roles: List các tên role được phép. VD: ['Admin', 'Bác sĩ']
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Chưa đăng nhập -> Đá về login
            if not current_user.is_authenticated:
                return redirect(url_for('auth_bp.login'))
            
            # 2. Lấy tên Role của user hiện tại
            # (Giả sử model Role có cột role_name)
            user_role = current_user.role.role_name if current_user.role else None

            # 3. Kiểm tra quyền
            # Nếu user là Admin thì luôn cho qua (Quyền lực tối cao)
            if user_role == 'Admin':
                return f(*args, **kwargs)
            
            # Nếu role của user không nằm trong danh sách cho phép -> Lỗi 403 (Cấm)
            if user_role not in allowed_roles:
                abort(403) # Trả về lỗi Forbidden
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator