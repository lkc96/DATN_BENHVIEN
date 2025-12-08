from flask import Blueprint, request, jsonify
from datetime import datetime
from app.extensions import db
from app.models import Account, Appointment, ClinicRoom, Position, Staff

appointment_bp = Blueprint('appointment', __name__)

@appointment_bp.route('/clinic-rooms', methods=['GET'])
def get_clinic_rooms():
    try:
        # Lấy tất cả phòng, hoặc lọc theo function chứa chữ "khám" nếu muốn
        rooms = ClinicRoom.query.filter(ClinicRoom.function== 'Khám bệnh').all()
        
        room_list = []
        for r in rooms:
            room_list.append({
                'room_id': r.room_id,
                'room_name': r.room_name,
                'room_number': r.room_number
            })
            
        return jsonify({'success': True, 'data': room_list})
    except Exception as e:
        print(f"Error get rooms: {e}")
        return jsonify({'success': False, 'data': []}), 500

# --- 2. API Đặt lịch (Cập nhật logic lưu room_id và service) ---
@appointment_bp.route('/book-appointment', methods=['POST'])
def book_appointment():
    data = request.get_json()
    account_id = data.get('account_id')
    
    date_str = data.get('date')
    time_slot = data.get('time')
    
    # [THAY ĐỔI] Nhận room_id và service thay vì doctor/specialty cũ
    room_id = data.get('room_id') 
    service_type = data.get('service_type') # "Khám bảo hiểm", "Tái khám"...

    if not all([account_id, date_str, time_slot, room_id, service_type]):
        return jsonify({'success': False, 'message': 'Vui lòng điền đầy đủ thông tin'}), 400

    try:
        account = Account.query.get(account_id)
        if not account or not account.patient:
            return jsonify({'success': False, 'message': 'Lỗi xác thực'}), 404
        
        # Xử lý thời gian
        start_time_str = time_slot.split(' - ')[0].strip()
        full_datetime_str = f"{date_str} {start_time_str}"
        appointment_datetime = datetime.strptime(full_datetime_str, '%d/%m/%Y %H:%M')

        # Tạo lịch hẹn
        new_appt = Appointment(
            patient_id=account.patient.patient_id,
            room_id=room_id,               # Lưu ID phòng
            appointment_time=appointment_datetime,
            reason=service_type,           # Lưu loại dịch vụ vào cột reason
            status='Chờ xác nhận'
        )

        db.session.add(new_appt)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Đặt lịch thành công!'})

    except Exception as e:
        print(f"Error Booking: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Lỗi hệ thống'}), 500

# --- 3. API Lấy danh sách (Cập nhật hiển thị) ---
@appointment_bp.route('/appointments', methods=['POST'])
def get_appointments():
    data = request.get_json()
    account_id = data.get('account_id')

    if not account_id:
        return jsonify({'success': False, 'message': 'Thiếu account_id'}), 400

    try:
        account = Account.query.get(account_id)
        if not account or not account.patient:
            return jsonify({'success': False, 'message': 'Không tìm thấy bệnh nhân'}), 404

        # Join bảng ClinicRoom để lấy tên phòng
        appointments = db.session.query(Appointment, ClinicRoom)\
            .join(ClinicRoom, Appointment.room_id == ClinicRoom.room_id)\
            .filter(Appointment.patient_id == account.patient.patient_id)\
            .order_by(Appointment.appointment_time.desc()).all()

        appt_list = []
        for appt, room in appointments:
            doctor_obj = db.session.query(Staff)\
                .join(Position, Staff.position_id == Position.position_id)\
                .filter(Staff.room_id == room.room_id)\
                .filter(Position.position_name.ilike('%Bác sĩ%'))\
                .first()
            
            doctor_name = doctor_obj.full_name if doctor_obj else "Bác sĩ trực"
            appt_list.append({
                "id": appt.appointment_id,
                "specialty": room.room_name,    # Tên phòng
                "doctor_name": doctor_name,     # [MỚI] Tên bác sĩ thật
                "service_type": appt.reason,    # [MỚI] Dịch vụ (Lý do khám)
                "date": appt.appointment_time.strftime('%d/%m/%Y'),
                "time": appt.appointment_time.strftime('%H:%M'),
                "status": appt.status,
                "room_number": room.room_number or ""
            })

        return jsonify({'success': True, 'data': appt_list})

    except Exception as e:
        print(f"Error Get Appt: {e}")
        return jsonify({'success': False, 'message': 'Lỗi hệ thống'}), 500