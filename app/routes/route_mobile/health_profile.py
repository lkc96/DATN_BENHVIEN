
from flask import Blueprint, request, jsonify
from app.extensions import db
# Import đúng tên Class từ models.py của bạn
from app.models import (
    Account, ExaminationSession, DiagnosisRecord, ClinicRoom, 
    Staff, Position, Prescription, PrescriptionDetail, Medicine, ICD10
)

health_bp = Blueprint('health', __name__)

@health_bp.route('/api/patient/medical-records', methods=['POST'])
def get_medical_records():
    data = request.get_json()
    account_id = data.get('account_id')

    if not account_id:
        return jsonify({'success': False, 'message': 'Thiếu account_id'}), 400

    try:
        # 1. Xác định bệnh nhân
        account = Account.query.get(account_id)
        if not account or not account.patient:
            return jsonify({'success': False, 'message': 'Lỗi xác thực'}), 404
        
        patient = account.patient

        # 2. Truy vấn lịch sử khám (Chỉ lấy đã hoàn thành)
        sessions = db.session.query(ExaminationSession, DiagnosisRecord, ClinicRoom)\
            .join(DiagnosisRecord, ExaminationSession.examination_id == DiagnosisRecord.examination_id)\
            .join(ClinicRoom, ExaminationSession.room_id == ClinicRoom.room_id)\
            .filter(ExaminationSession.patient_id == patient.patient_id)\
            .filter(ExaminationSession.status == 'Hoàn thành') \
            .order_by(ExaminationSession.create_date.desc())\
            .all()

        record_list = []
        
        for session, diagnosis, room in sessions:
            # 2.1 Tìm Bác sĩ
            doctor = db.session.query(Staff)\
                .join(Position, Staff.position_id == Position.position_id)\
                .filter(Staff.room_id == room.room_id)\
                .filter(Position.position_name.ilike('%Bác sĩ%'))\
                .first()
            doctor_name = doctor.full_name if doctor else "Bác sĩ chuyên khoa"

           
            prescription = Prescription.query.filter_by(examination_session_id=session.examination_id).first()
            
            medicine_list = []
            if prescription:
                
                details = db.session.query(PrescriptionDetail, Medicine)\
                    .join(Medicine, PrescriptionDetail.medicine_id == Medicine.medicine_id)\
                    .filter(PrescriptionDetail.prescription_id == prescription.prescription_id)\
                    .all()
                
                for detail, med in details:
                    medicine_list.append({
                        "medicine_name": med.medicine_name,
                        "quantity": detail.quantity,
                        "unit": med.unit or "Viên",
                        "dosage": detail.dosage or "Theo chỉ dẫn"
                    })

            # Nếu có mã bệnh ICD10, ưu tiên lấy Tên từ bảng ICD10
            if diagnosis.main_icd:
                # Hiển thị kiểu: "Tên bệnh (Mã)" -> VD: "Viêm dạ dày cấp (K29.1)"
                disease_display = f"{diagnosis.main_icd.name} ({diagnosis.main_disease_code})"
            elif diagnosis.main_disease_code:
                # Nếu có mã mà không tìm thấy tên trong bảng ICD10, hiển thị mã tạm
                disease_display = diagnosis.main_disease_code
            
            
            # 2.3 Tổng hợp dữ liệu
            record_list.append({
                "session_id": session.examination_id,
                "date": session.create_date.strftime('%d/%m/%Y'),
                "time": session.create_date.strftime('%H:%M'),
                "department": room.room_name,
                "doctor": doctor_name,
                "diagnosis": disease_display,
                "advice":  diagnosis.doctor_advice or session.doctor_advice or "Không có lời dặn",
                "medicines": medicine_list 
            })

        return jsonify({
            'success': True,
            'data': record_list
        })

    except Exception as e:
        print(f"Error Medical Records: {e}")
        return jsonify({'success': False, 'message': 'Lỗi hệ thống'}), 500