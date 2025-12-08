from app.models import Account, Patient, MagneticCard
from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/api/patient/profile', methods=['POST'])
def get_patient_profile():
    data = request.get_json()
    account_id = data.get('account_id')

    if not account_id:
        return jsonify({'success': False, 'message': 'Thiếu account_id'}), 400

    try:
        # 1. Tìm Account và Patient tương ứng
        account = Account.query.get(account_id)
        
        if not account:
            return jsonify({'success': False, 'message': 'Tài khoản không tồn tại'}), 404
            
        # Lấy thông tin bệnh nhân từ quan hệ account.patient
        patient = account.patient

        if not patient:
            return jsonify({'success': False, 'message': 'Chưa có hồ sơ bệnh nhân'}), 404
        card = MagneticCard.query.filter_by(patient_id=patient.patient_id).first()
        if card and card.card_code:
            patient_code = f"BN{card.card_code}"
        else:
            # Fallback nếu chưa có thẻ: BN + ID bệnh nhân (hoặc để "Chưa cấp thẻ")
            patient_code = f"BN{patient.patient_id:06d}"
        # 2. Chuẩn bị dữ liệu trả về
        # Xử lý ngày sinh: convert từ date object sang string dd/mm/yyyy
        dob_str = "Chưa cập nhật"
        if patient.date_birth:
            dob_str = patient.date_birth.strftime('%d/%m/%Y')

        profile_data = {
            "name": patient.full_name,
            "patient_code": patient_code, 
            "phone": patient.phone or "Chưa cập nhật",
            "email": account.email, # Email lấy từ bảng Account
            "address": patient.address or "Chưa cập nhật",
            "dob": dob_str,
            "gender": patient.gender or "Khác",
            "id_number": patient.id_number or "Chưa cập nhật" # Dùng làm số BHYT/CCCD
        }

        return jsonify({
            'success': True,
            'data': profile_data
        })

    except Exception as e:
        print(f"Error Profile: {e}")
        return jsonify({'success': False, 'message': 'Lỗi hệ thống'}), 500
    
@profile_bp.route('/api/account/change-password', methods=['POST'])
def change_password():
    data = request.get_json()
    account_id = data.get('account_id')
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not all([account_id, old_password, new_password]):
        return jsonify({'success': False, 'message': 'Vui lòng nhập đầy đủ thông tin'}), 400

    try:
        # 1. Tìm tài khoản
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'success': False, 'message': 'Tài khoản không tồn tại'}), 404

        # 2. Kiểm tra mật khẩu cũ
        if not check_password_hash(account.password, old_password):
            return jsonify({'success': False, 'message': 'Mật khẩu cũ không chính xác'}), 400

        # 3. Cập nhật mật khẩu mới (Mã hóa trước khi lưu)
        account.password = generate_password_hash(new_password)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Đổi mật khẩu thành công'})

    except Exception as e:
        print(f"Error Change Password: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Lỗi hệ thống'}), 500