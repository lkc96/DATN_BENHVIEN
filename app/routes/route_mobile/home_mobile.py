from flask import Blueprint, request, jsonify
from sqlalchemy import desc
from app.extensions import db
from app.models import (
    Patient, ExaminationSession, DiagnosisRecord, Appointment, Account, 
    SessionRooms, ClinicRoom, Staff, Position, MagneticCard
)
from datetime import datetime, date
from sqlalchemy import func

home_bp = Blueprint('home', __name__)

@home_bp.route('/api/patient/home-data', methods=['POST'])
def get_home_data():
    data = request.get_json()
    account_id = data.get('account_id') # Lấy account_id từ lúc Login gửi sang

    if not account_id:
        return jsonify({'success': False, 'message': 'Thiếu account_id'}), 400

    try:
        # 1. Lấy thông tin Bệnh nhân
        account = Account.query.get(account_id)
        if not account or not account.patient:
            return jsonify({'success': False, 'message': 'Không tìm thấy hồ sơ bệnh nhân'}), 404
        
        patient = account.patient
        
        # 2. Lấy chỉ số sức khỏe (Từ lần khám gần nhất có ghi chép chẩn đoán)
        # Logic: Tìm Session khám gần nhất của bệnh nhân -> Lấy DiagnosisRecord của session đó
        record = DiagnosisRecord.query\
            .join(ExaminationSession, DiagnosisRecord.examination_id == ExaminationSession.examination_id)\
            .filter(ExaminationSession.patient_id == patient.patient_id)\
            .order_by(ExaminationSession.create_date.desc())\
            .first()
            
        health_stats = {
            "heart_rate": "--",
            "blood_pressure": "--/--", 
            "temperature": "--"
        }

        # Nếu tìm thấy hồ sơ bệnh án
        if record:
            print(f"DEBUG: Tìm thấy record ID {record.record_id}") # In ra console để kiểm tra
            health_stats = {
                # Chuyển số thành chuỗi để tránh lỗi JSON
                "heart_rate": str(int(record.pulse)) if record.pulse else "--",
                "blood_pressure": str(record.blood_pressure) if record.blood_pressure else "--/--",
                "temperature": str(record.temperature) if record.temperature else "--"
            }
        else:
            print("DEBUG: Không tìm thấy hồ sơ sức khỏe nào.")

        # 1. Lấy danh sách các phòng bệnh nhân đang xếp hàng (Không join Staff ở đây)
        queues = db.session.query(SessionRooms, ClinicRoom)\
            .join(ExaminationSession, SessionRooms.examination_id == ExaminationSession.examination_id)\
            .join(ClinicRoom, SessionRooms.room_id == ClinicRoom.room_id)\
            .filter(ExaminationSession.patient_id == patient.patient_id)\
            .filter(func.date(SessionRooms.create_date) == date.today()) \
            .order_by(SessionRooms.session_room_id.desc())\
            .all()

        queue_list = []
        
        for s_room, c_room in queues:
            my_number = s_room.number_order
            
            # --- [SỬA ĐỔI QUAN TRỌNG: LẤY SỐ ĐANG KHÁM THẬT] ---
            # Tìm xem ai đang có trạng thái 'Đang khám' tại phòng này hôm nay
            active_session = db.session.query(SessionRooms)\
                .filter(
                    SessionRooms.room_id == c_room.room_id,
                    SessionRooms.create_date == date.today(),
                    SessionRooms.status == 'Đang khám' # Lọc theo trạng thái
                )\
                .order_by(SessionRooms.number_order.desc())\
                .first()

            if active_session:
                current_number = active_session.number_order
            else:
                # Nếu không có ai đang khám, tìm số chờ nhỏ nhất hiện tại
                # Để biết "đến số mấy rồi"
                min_waiting = db.session.query(func.min(SessionRooms.number_order))\
                    .filter(
                        SessionRooms.room_id == c_room.room_id,
                        SessionRooms.create_date == date.today(),
                        SessionRooms.status == 'Đang chờ'
                    ).scalar()
                
                # Nếu có người chờ thì số hiện tại coi như là (số nhỏ nhất - 1)
                # Nếu không ai chờ, không ai khám -> Coi như là 0
                current_number = (min_waiting - 1) if min_waiting else 0
            
            # 2. Tìm chính xác Bác sĩ của phòng này
            # Logic: Tìm Staff thuộc phòng này VÀ có Position chứa chữ "Bác sĩ"
            doctor = db.session.query(Staff)\
                .join(Position, Staff.position_id == Position.position_id)\
                .filter(Staff.room_id == c_room.room_id)\
                .filter(Position.position_name.ilike('%Bác sĩ%'))\
                .first() 
            
            # .ilike('%Bác sĩ%'): Tìm kiếm không phân biệt hoa thường, 
            # chấp nhận cả "Bác sĩ", "Bác sĩ chuyên khoa", "Thạc sĩ Bác sĩ"...
            
            # Nếu tìm thấy thì lấy tên, không thì để trống hoặc hiển thị tên phòng
            doctor_name = doctor.full_name if doctor else c_room.room_name 

            queue_list.append({
                "room_name": c_room.room_name,
                "room_number": c_room.room_number or "",
                "doctor_name": doctor_name,
                "my_number": my_number,
                "current_number": current_number,
                "status": s_room.status
            })
        # Tìm thẻ từ liên kết với bệnh nhân này
        #card = MagneticCard.query.filter_by(patient_id=patient.patient_id).first()
        card = db.session.query(MagneticCard)\
            .join(Patient, MagneticCard.patient_id == Patient.patient_id)\
            .filter(Patient.patient_id == patient.patient_id)\
            .first()
        # Nếu có thẻ thì lấy số dư, không thì bằng 0
        current_balance = 0
        if card:
            current_balance = float(card.balance)

        return jsonify({
            'success': True,
            'data': {
                'full_name': patient.full_name,
                'health_stats': health_stats,
                'clinic_queues': queue_list, # Trả về danh sách Queue thay vì appointment
                'balance': current_balance,
            }
        })

    except Exception as e:
        print(f"Error Home Data: {e}")
        return jsonify({'success': False, 'message': 'Lỗi hệ thống'}), 500