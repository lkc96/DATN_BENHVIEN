from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from app.extensions import db
from app.models import Account, Staff, Patient

auth_mobile_bp = Blueprint('auth', __name__)

@auth_mobile_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    # 1. Nhận username và password từ Flutter
    username_input = data.get('username')
    password_input = data.get('password')

    if not username_input or not password_input:
        return jsonify({'success': False, 'message': 'Vui lòng nhập Username và Mật khẩu'}), 400

    try:
        # 2. Tìm tài khoản theo username trong bảng accounts
        account = Account.query.filter_by(username=username_input).first()

        # 3. Kiểm tra logic:
        # - Có tài khoản không?
        # - Role có phải là 5 không?
        # - Mật khẩu giải mã có khớp không?
        if account:
            if account.role_id != 5:
                 return jsonify({'success': False, 'message': 'Tài khoản này không phải là Bệnh nhân (Role != 5)'}), 403
            
            # So sánh mật khẩu nhập vào (raw) với mật khẩu mã hóa trong DB (hash)
            if check_password_hash(account.password, password_input):
                
                # Lấy tên hiển thị từ bảng Patient nếu có
                full_name = account.username
                if account.patient:
                    full_name = account.patient.full_name

                return jsonify({
                    'success': True,
                    'message': 'Đăng nhập thành công',
                    'data': {
                        'account_id': account.account_id,
                        'username': account.username,
                        'role_id': account.role_id,
                        'full_name': full_name
                    }
                }), 200
            else:
                return jsonify({'success': False, 'message': 'Mật khẩu không chính xác'}), 401
        else:
            return jsonify({'success': False, 'message': 'Tài khoản không tồn tại'}), 401

    except Exception as e:
        print(f"Lỗi Server: {e}")
        return jsonify({'success': False, 'message': 'Lỗi hệ thống'}), 500