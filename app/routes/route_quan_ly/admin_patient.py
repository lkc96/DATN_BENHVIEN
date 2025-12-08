from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models import Patient, Account, MagneticCard
from werkzeug.security import generate_password_hash
from sqlalchemy import or_
from datetime import datetime

from app.decorators import role_required

admin_patient_bp = Blueprint('admin_patient_bp', __name__)

@admin_patient_bp.route('/admin/quan-ly-benh-nhan', methods=['GET'])
@role_required(['Admin', 'Lễ tân'])
def index():
    return render_template('quan_ly/quan_ly_benh_nhan.html')

# 1. API LẤY DANH SÁCH (KÈM ACCOUNT & CARD)
@admin_patient_bp.route('/api/admin/patients', methods=['GET'])
def get_patients():
    try:
        page = request.args.get('page', 1, type=int)
        keyword = request.args.get('keyword', '').strip()
        per_page = 8 

        # Join 3 bảng: Patient -> Account (Left Join) -> MagneticCard (Left Join)
        query = db.session.query(Patient, Account, MagneticCard)\
            .outerjoin(Account, Patient.account_id == Account.account_id)\
            .outerjoin(MagneticCard, Patient.patient_id == MagneticCard.patient_id)

        # [TÌM KIẾM]
        if keyword:
            search_str = f"%{keyword}%"
            query = query.filter(or_(
                Patient.full_name.ilike(search_str),
                Patient.phone.ilike(search_str),
                Patient.id_number.ilike(search_str),
                MagneticCard.card_code.ilike(search_str) # Tìm theo mã thẻ
            ))

        query = query.distinct(Patient.patient_id).order_by(Patient.patient_id.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        data = []
        for p, acc, card in pagination.items:
            data.append({
                # Thông tin cá nhân
                'id': p.patient_id,
                'full_name': p.full_name,
                'date_birth': p.date_birth.strftime('%Y-%m-%d') if p.date_birth else '',
                'gender': p.gender,
                'phone': p.phone,
                'address': p.address,
                'id_number': p.id_number,
                
                # Thông tin tài khoản
                'account_id': acc.account_id if acc else None,
                'username': acc.username if acc else '',
                'email': acc.email if acc else '',
                
                # Thông tin thẻ
                'card_id': card.card_id if card else None,
                'card_code': card.card_code if card else '',
                'card_balance': float(card.balance) if card else 0,
                'card_status': card.status if card else 'Chưa cấp'
            })
            
        return jsonify({
            'success': True, 
            'data': data,
            'pagination': {
                'current_page': page,
                'total_pages': pagination.pages,
                'total_records': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)}), 500

# 2. API LƯU (THÊM / SỬA TỔNG HỢP)
@admin_patient_bp.route('/api/admin/patient/save', methods=['POST'])
@role_required(['Admin', 'Lễ tân'])
def save_patient():
    try:
        data = request.json
        patient_id = data.get('id')
        
        # Data Patient
        full_name = data.get('full_name')
        date_birth_str = data.get('date_birth')
        gender = data.get('gender')
        phone = data.get('phone')
        address = data.get('address')
        id_number = data.get('id_number')
        
        # Data Account
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        
        # Data Card
        card_code = data.get('card_code')
        card_status = data.get('card_status', 'Active')

        if not full_name: return jsonify({'success': False, 'message': 'Họ tên là bắt buộc'}), 400

        # Xử lý ngày sinh
        date_birth = None
        if date_birth_str:
            try:
                date_birth = datetime.strptime(date_birth_str, '%Y-%m-%d').date()
            except: pass

        # --- XỬ LÝ: THÊM MỚI ---
        if not patient_id:
            # 1. Tạo Account (Nếu có nhập username)
            new_acc = None
            if username:
                if Account.query.filter_by(username=username).first():
                    return jsonify({'success': False, 'message': 'Tên đăng nhập đã tồn tại!'}), 400
                new_acc = Account(username=username, email=email)
                new_acc.set_password(password if password else '123456')
                db.session.add(new_acc)
                db.session.flush() # Để lấy account_id

            # 2. Tạo Patient
            new_patient = Patient(
                full_name=full_name, date_birth=date_birth, gender=gender,
                phone=phone, address=address, id_number=id_number,
                account_id=new_acc.account_id if new_acc else None
            )
            db.session.add(new_patient)
            db.session.flush() # Để lấy patient_id

            # 3. Tạo Card (Nếu có mã thẻ)
            if card_code:
                if MagneticCard.query.filter_by(card_code=card_code).first():
                    return jsonify({'success': False, 'message': 'Mã thẻ từ này đã được sử dụng!'}), 400
                
                new_card = MagneticCard(
                    patient_id=new_patient.patient_id,
                    card_code=card_code,
                    status=card_status,
                    balance=0
                )
                db.session.add(new_card)
                db.session.flush()
                # Cập nhật ngược lại bảng Patient
                new_patient.card_id = new_card.card_id

            msg = 'Thêm hồ sơ bệnh nhân thành công'

        # --- XỬ LÝ: CẬP NHẬT ---
        else:
            patient = Patient.query.get(patient_id)
            if not patient: return jsonify({'success': False, 'message': 'Không tìm thấy'}), 404
            
            # Update Patient Info
            patient.full_name = full_name
            patient.date_birth = date_birth
            patient.gender = gender
            patient.phone = phone
            patient.address = address
            patient.id_number = id_number
            
            # Update/Create Account
            if username:
                if patient.account_id:
                    acc = Account.query.get(patient.account_id)
                    acc.email = email
                    if password: acc.set_password(password)
                else:
                    # Chưa có tk thì tạo mới
                    new_acc = Account(username=username, email=email)
                    new_acc.set_password(password if password else '123456')
                    db.session.add(new_acc)
                    db.session.flush()
                    patient.account_id = new_acc.account_id
            
            # Update/Create Card
            if card_code:
                # Kiểm tra thẻ có tồn tại ở bệnh nhân KHÁC không
                exist_card = MagneticCard.query.filter_by(card_code=card_code).first()
                if exist_card and exist_card.patient_id != patient.patient_id:
                     return jsonify({'success': False, 'message': 'Mã thẻ này đang thuộc về người khác'}), 400

                # Tìm thẻ của bệnh nhân này
                my_card = MagneticCard.query.filter_by(patient_id=patient.patient_id).first()
                if my_card:
                    my_card.card_code = card_code
                    my_card.status = card_status
                else:
                    # Tạo thẻ mới
                    new_card = MagneticCard(
                        patient_id=patient.patient_id,
                        card_code=card_code,
                        status=card_status,
                        balance=0
                    )
                    db.session.add(new_card)
                    db.session.flush()
                    patient.card_id = new_card.card_id

            msg = 'Cập nhật hồ sơ thành công'

        db.session.commit()
        return jsonify({'success': True, 'message': msg})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# 3. API XÓA (Giữ nguyên logic cũ)
@admin_patient_bp.route('/api/admin/patient/delete/<int:id>', methods=['DELETE'])
@role_required(['Admin', 'Lễ tân'])
def delete_patient(id):
    try:
        patient = Patient.query.get(id)
        if not patient: return jsonify({'success': False}), 404
        
        # Xóa Account và Card liên quan trước (nếu muốn xóa sạch)
        # Tuy nhiên, an toàn nhất là chỉ xóa Patient, nếu DB có Cascade thì tự bay
        # Ở đây ta xử lý xóa thủ công để đảm bảo sạch rác
        
        acc_id = patient.account_id
        
        # Xóa thẻ trước
        MagneticCard.query.filter_by(patient_id=id).delete()
        
        # Xóa bệnh nhân
        db.session.delete(patient)
        
        # Xóa tài khoản
        if acc_id:
            Account.query.filter_by(account_id=acc_id).delete()

        db.session.commit()
        return jsonify({'success': True, 'message': 'Đã xóa bệnh nhân và dữ liệu liên quan'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Không thể xóa (Có thể do đã có lịch sử khám)'}), 500