from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models import (
    ExaminationSession, Patient, SessionRooms, ClinicRoom, Invoice, InvoiceDetail, Medicine, Prescription, PrescriptionDetail,
    MagneticCard, ICD10, DiagnosisRecord,Service, ServiceOrder,CatalogServices, Staff, Expertise)
from sqlalchemy import desc, func, or_, and_
from datetime import datetime, time
from app.socket_events import send_notification
import time
from flask_login import current_user

from app.decorators import role_required

kham_benh_bp = Blueprint('kham_benh', __name__)

@kham_benh_bp.route('/quan-ly-kham-benh')
@role_required(['Admin', 'Bác sĩ', 'Điều dưỡng'])
def index():
    rooms = ClinicRoom.query.all()
    return render_template('kham_benh/danh_sach.html', rooms=rooms)

@kham_benh_bp.route('/api/kham-benh/danh-sach-cho', methods=['GET'])
@role_required(['Admin', 'Bác sĩ', 'Điều dưỡng'])
def get_waiting_list():
    try:
        # Lấy tham số từ request
        room_id = request.args.get('room_id')
        keyword = request.args.get('keyword', '').strip()
        date_filter = request.args.get('date', '')
        page = request.args.get('page', 1, type=int)
        per_page = 10 

        # --- [BẮT ĐẦU SỬA: LOGIC PHÂN QUYỀN PHÒNG] ---
        current_staff_room_id = None
        
        # Kiểm tra nếu user đã đăng nhập và là nhân viên
        if current_user.is_authenticated and current_user.staff:
            current_staff_room_id = current_user.staff.room_id
            
            # Kiểm tra xem có phải Admin không? (Admin được xem tất cả)
            is_admin = False
            if current_user.role and current_user.role.role_name in ['Admin', 'Quản trị']:
                is_admin = True
            
            # Nếu KHÔNG phải Admin và đã được gán phòng -> Bắt buộc lọc theo phòng đó
            if not is_admin and current_staff_room_id:
                room_id = str(current_staff_room_id)
        # --- [KẾT THÚC SỬA] ---

        # Query cơ bản: Join 3 bảng SessionRooms -> ExaminationSession -> Patient
        query = db.session.query(SessionRooms, ExaminationSession, Patient, ClinicRoom)\
            .join(ExaminationSession, SessionRooms.examination_id == ExaminationSession.examination_id)\
            .join(Patient, ExaminationSession.patient_id == Patient.patient_id)\
            .join(ClinicRoom, SessionRooms.room_id == ClinicRoom.room_id)
        
        query = query.filter(ClinicRoom.function == 'Khám bệnh')

        # 1. Lọc theo Phòng khám (Biến room_id đã được xử lý ở logic trên)
        if room_id and room_id != 'all':
            query = query.filter(SessionRooms.room_id == int(room_id))
        
        # Lọc theo từ khóa
        if keyword:
            clean_kw = keyword.replace("BN", "")
            query = query.filter(db.or_(
                Patient.full_name.ilike(f"%{keyword}%"),
                MagneticCard.card_code.like(f"%{clean_kw}%")
            ))

        # 2. LỌC THEO NGÀY 
        start_date = None
        end_date = None

        if date_filter:
            if " to " in date_filter:
                parts = date_filter.split(" to ")
                start_str = parts[0].strip()
                end_str = parts[1].strip()
                
                start_date = datetime.strptime(start_str, '%d/%m/%Y')
                end_date = datetime.strptime(end_str, '%d/%m/%Y')
            else:
                try:
                    target_date = datetime.strptime(date_filter.strip(), '%d/%m/%Y')
                    start_date = target_date
                    end_date = target_date
                except ValueError:
                    pass 
        else:
            # Mặc định lấy HÔM NAY
            today = datetime.now().date()
            start_date = datetime.combine(today, time.min) 
            end_date = datetime.combine(today, time.max)

        # ÁP DỤNG QUERY LỌC NGÀY
        if start_date and end_date:
            start_time = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(ExaminationSession.create_date.between(start_time, end_time))

        # Sắp xếp: Ưu tiên trạng thái đang khám, sau đó đến số thứ tự
        query = query.order_by(SessionRooms.number_order.asc())

        # Phân trang
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        data = pagination.items
        
        result = []
        for sess_room, exam_sess, patient, room in data:
            card = MagneticCard.query.filter_by(patient_id=patient.patient_id).first()
            ma_bn = f"BN{card.card_code}" if card else f"P{patient.patient_id}"

            # Map trạng thái
            status_map = {
                'Tiếp nhận': '<span class="badge bg-info">Tiếp nhận</span>',
                'Chờ khám': '<span class="badge bg-primary text-dark">Chờ khám</span>',
                'Đang khám': '<span class="badge bg-warning">Đang khám</span>',
                'Hoàn thành': '<span class="badge bg-success">Hoàn thành</span>'
            }
            
            if exam_sess.status == 'Chờ khám':
                 status_display = '<span class="badge bg-primary">Chờ khám</span>'
            elif exam_sess.status == 'Đang khám':
                 status_display = '<span class="badge bg-warning text-dark">Đang khám</span>'
            else:
                 status_display = status_map.get(exam_sess.status, exam_sess.status)

            result.append({
                'ma_dk': f"DK{exam_sess.examination_id:09d}",
                'thoi_gian': exam_sess.create_date.strftime('%d/%m/%Y %H:%M:%S'),
                'stt': sess_room.number_order,
                'ho_ten': patient.full_name,
                'ma_bn': ma_bn,
                'gioi_tinh': patient.gender,
                'nam_sinh': patient.date_birth.year if patient.date_birth else '',
                'sdt': patient.phone,
                'phong_kham': room.room_name if room else '',
                'trang_thai': status_display,
                'exam_id': exam_sess.examination_id
            })

        return jsonify({
            'success': True, 
            'current_room_id': current_staff_room_id, # Trả về ID phòng để frontend biết (nếu cần)
            'data': result,
            'pagination': {
                'current_page': page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': per_page
            }          
        })

    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)}), 500


# API LẤY CHI TIẾT PHIẾU KHÁM
@kham_benh_bp.route('/api/kham-benh/chi-tiet/<int:exam_id>', methods=['GET'])
@role_required(['Admin', 'Bác sĩ', 'Điều dưỡng'])
def get_exam_detail(exam_id):
    try:
        # 1. Lấy thông tin cơ bản (Code cũ)
        session = ExaminationSession.query.get(exam_id)
        if not session:
            return jsonify({'success': False, 'message': 'Không tìm thấy phiếu'}), 404
            
        patient = Patient.query.get(session.patient_id)
        room = ClinicRoom.query.get(session.room_id)
        card = MagneticCard.query.filter_by(patient_id=patient.patient_id).first()

        # Ưu tiên lấy bác sĩ đã gán cho phiên khám này
        doctor_name = ""
        # Kiểm tra xem phiên khám có phòng không
        if session.room_id:
            # Tìm nhân viên (Staff) được gán cho phòng này
            # Lưu ý: Nếu phòng có nhiều nhân viên, lệnh này lấy người đầu tiên tìm thấy
            staff = Staff.query.filter_by(room_id=session.room_id).first()
            
            if staff:
                # Có thể thêm logic kiểm tra chức vụ nếu cần (VD: staff.position_id == 1)
                doctor_name = staff.full_name
        # ---------------------------------------------

        age = 0
        if patient.date_birth:
            age = datetime.now().year - patient.date_birth.year

        # 2. [MỚI] Lấy thông tin Chẩn đoán cũ (Nếu có)
        record = DiagnosisRecord.query.filter_by(examination_id=exam_id).first()
        
        diagnosis_data = {}
        if record:
            # Lấy tên bệnh chính từ bảng ICD10 để hiển thị đẹp (VD: J00 - Viêm họng)
            icd_name = ""
            if record.main_disease_code:
                icd = ICD10.query.get(record.main_disease_code)
                if icd:
                    icd_name = f"{icd.code} - {icd.name}"

            diagnosis_data = {
                'height': float(record.height) if record.height else '',
                'weight': float(record.weight) if record.weight else '',
                'bmi': float(record.bmi) if record.bmi else '',
                'temperature': float(record.temperature) if record.temperature else '',
                'pulse': record.pulse or '',
                'blood_pressure': record.blood_pressure or '',
                
                'clinical_symptoms': record.clinical_symptoms or session.reason, # Ưu tiên lấy trong record, nếu ko có lấy lý do khám
                'initial_diagnosis': record.clinical_symptoms or '', # Lưu ý: Map đúng trường DB của bạn
                
                'main_disease': icd_name, # Chuỗi "J00 - Tên bệnh"
                'sub_disease': record.sub_disease_code or '',
                
                'treatment_plan': record.treatment_plan or '',
                'doctor_advice': record.doctor_advice or ''
            }

        # 3. Tổng hợp dữ liệu trả về
        data = {
            'patient_id': patient.patient_id,
            'ma_bn': f"BN{card.card_code}" if card else f"P{patient.patient_id}",
            'ho_ten': patient.full_name,
            'ngay_sinh': patient.date_birth.strftime('%d/%m/%Y') if patient.date_birth else '',
            'gioi_tinh': patient.gender,
            'tuoi': age,
            'phong_kham': f"{room.room_number} - {room.room_name}" if room else '',
            'dia_chi': patient.address or '',
            'bac_si': doctor_name,
            # Trả về cục data khám cũ (nếu chưa khám thì nó là rỗng)
            'kham_data': diagnosis_data 
        }
        
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)}), 500


@kham_benh_bp.route('/api/icd10/search', methods=['GET'])
def search_icd10():
    try:
        keyword = request.args.get('keyword', '').strip()
        
        # Nếu chưa gõ gì thì không trả về
        if not keyword:
            return jsonify({'success': True, 'data': []})

        # Tìm kiếm theo Mã hoặc Tên (Không phân biệt hoa thường - ilike)
        # Giới hạn 20 kết quả để query nhanh
        results = ICD10.query.filter(
            or_(
                ICD10.code.ilike(f"%{keyword}%"),
                ICD10.name.ilike(f"%{keyword}%")
            )
        ).limit(20).all()

        # Chuyển object thành dict
        data = [item.to_dict() for item in results]
        
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        print("Lỗi tìm ICD10:", e)
        return jsonify({'success': False, 'message': str(e)}), 500

@kham_benh_bp.route('/api/kham-benh/luu-chan-doan', methods=['POST'])
def save_diagnosis():
    try:
        data = request.json
        exam_id = data.get('exam_id')
        
        if not exam_id:
            return jsonify({'success': False, 'message': 'Thiếu ID phiếu khám'}), 400

        record = DiagnosisRecord.query.filter_by(examination_id=exam_id).first()
        if not record:
            record = DiagnosisRecord(examination_id=exam_id)
            db.session.add(record)

        
        def get_float(val):
            if val is None: return None
            if isinstance(val, (int, float)): return float(val) # Nếu là số thì lấy luôn
            if isinstance(val, str):
                if val.strip() == '': return None
                try: return float(val)
                except: return None
            return None
        
        def get_int(val):
            if val is None: return None
            if isinstance(val, (int, float)): return int(val)
            if isinstance(val, str):
                if val.strip() == '': return None
                try: return int(val)
                except: return None
            return None

        
        record.height = get_float(data.get('chieu_cao'))
        record.weight = get_float(data.get('can_nang'))
        record.bmi = get_float(data.get('bmi'))
        record.temperature = get_float(data.get('nhiet_do'))
        record.pulse = get_int(data.get('mach'))
        record.blood_pressure = data.get('huyet_ap')
        # 2. Lưu Chẩn đoán
        record.clinical_symptoms = data.get('ly_do_kham') # Hoặc map từ triệu chứng
        record.treatment_plan = data.get('huong_xu_ly')
        record.doctor_advice = data.get('loi_dan')

        ngay_hen_str = data.get('ngay_hen') # Nhận chuỗi 'YYYY-MM-DD'
        
        if ngay_hen_str:
            try:
                # 1. Chuyển chuỗi thành datetime object
                dt_obj = datetime.strptime(ngay_hen_str, '%Y-%m-%d')
                
                # 2. Lấy phần ngày (Date) từ datetime object
                record.re_examination_date = dt_obj.date() 
            except ValueError:
                record.re_examination_date = None 
        else:
            record.re_examination_date = None
        
        # Bỏ qua medical_history, physical_exam... vì bảng SQL không có

        # 3. Xử lý ICD-10
        main_icd_str = data.get('benh_chinh', '')
        if main_icd_str and ' - ' in main_icd_str:
            record.main_disease_code = main_icd_str.split(' - ')[0]
        else:
            record.main_disease_code = None

        record.sub_disease_code = data.get('benh_phu') # SQL dùng sub_disease_code
        # --- PHẦN 2: LƯU CHẨN ĐOÁN VÀO EXAMINATIONSESSION (YÊU CẦU CỦA BẠN) ---
        session = ExaminationSession.query.get(exam_id)
        if session:
            # 1. Lấy dữ liệu bệnh chính/phụ gửi lên
            main_disease = data.get('benh_chinh', '').strip() # VD: J00 - Viêm họng
            sub_disease = data.get('benh_phu', '').strip()    # VD: E11 - Tiểu đường

            # 2. Ghép chuỗi để hiển thị tổng quát
            final_diagnosis = main_disease
            if sub_disease:
                final_diagnosis += f", {sub_disease}"
            
            # 3. Lưu vào cột diagnosis của bảng Session
            session.diagnosis = final_diagnosis
            
            # Lưu luôn lời dặn vào bảng Session (nếu cần hiển thị ở danh sách)
            if data.get('loi_dan'):
                session.doctor_advice = data.get('loi_dan')
            if  session.status in ['Chờ khám', 'Tiếp nhận']:
                session.status = 'Đang khám'
    
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Lưu thành công!'})

    except Exception as e:
        db.session.rollback()
        print("Lỗi:", e)
        return jsonify({'success': False, 'message': str(e)}), 500


# API LẤY DANH SÁCH DỊCH VỤ (Để chọn)
@kham_benh_bp.route('/api/dich-vu/all', methods=['GET'])
def get_all_services():
    try:
        # Join bảng Service với CatalogServices để lấy tên nhóm
        services = db.session.query(Service, CatalogServices)\
            .join(CatalogServices, Service.catalogservice_id == CatalogServices.catalogservice_id)\
            .all()
        
        data = []
        for s, cat in services:
            data.append({
                'id': s.service_id,
                'name': s.service_name,
                'price': float(s.unit_price),
                
                # Trả về tên nhóm gốc trong CSDL (VD: "Xét nghiệm máu", "Siêu âm")
                # Để JS tự xử lý phân loại
                'catalog_name': cat.catalogservice_name 
            })
            
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        print("Lỗi lấy dịch vụ:", e)
        return jsonify({'success': False, 'message': str(e)}), 500

# API LẤY DANH SÁCH ĐÃ CHỈ ĐỊNH
@kham_benh_bp.route('/api/kham-benh/dich-vu-da-chon/<int:exam_id>', methods=['GET'])
def get_assigned_services(exam_id):
    orders = ServiceOrder.query.filter_by(examination_id=exam_id).all()
    result = []
    total_amount = 0
    
    for order in orders:
        service = Service.query.get(order.service_id)
        # Giả sử số lượng là 1 nếu model chưa có cột quantit
        qty = 1 
        price = float(service.unit_price) if service else 0
        total = price * qty
        total_amount += total
        
        result.append({
            'order_id': order.service_order_id,
            'service_name': service.service_name if service else 'Unknown',
            'quantity': qty,
            'price': price,
            'total': total,
            'status': order.status
        })
        
    return jsonify({
        'success': True, 
        'data': result, 
        'total_count': len(result),
        'total_amount': total_amount
    })


# API XÓA CHỈ ĐỊNH
@kham_benh_bp.route('/api/kham-benh/xoa-dich-vu/<int:order_id>', methods=['DELETE'])
def delete_service_order(order_id):
    try:
        order = ServiceOrder.query.get(order_id)
        if order:
            db.session.delete(order)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Không tìm thấy'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

#API LẤY DANH SÁCH CÁC PHIẾU CHỈ ĐỊNH CỦA BỆNH NHÂN
@kham_benh_bp.route('/api/kham-benh/danh-sach-phieu/<int:exam_id>', methods=['GET'])
def get_service_tickets(exam_id):
    # Lấy các mã phiếu duy nhất (distinct)
    tickets = db.session.query(ServiceOrder.ticket_code)\
        .filter_by(examination_id=exam_id)\
        .distinct().all()
    
    # Trả về danh sách mã phiếu
    # Lọc bỏ None nếu có
    data = [{'code': t.ticket_code, 'name': f"Phiếu {t.ticket_code}"} for t in tickets if t.ticket_code]
    return jsonify({'success': True, 'data': data})

# API LẤY CHI TIẾT DỊCH VỤ THEO MÃ PHIẾU
@kham_benh_bp.route('/api/kham-benh/chi-tiet-phieu', methods=['GET'])
def get_services_by_ticket():
    exam_id = request.args.get('exam_id')
    ticket_code = request.args.get('ticket_code')
    
    query = ServiceOrder.query.filter_by(examination_id=exam_id)
    
    if ticket_code and ticket_code != 'new':
        query = query.filter_by(ticket_code=ticket_code)
    
    orders = query.all()
    
    result = []
    total_amount = 0
    
    for order in orders:
        service = Service.query.get(order.service_id)
        # Giả định số lượng = 1 (hoặc lấy từ DB nếu có cột quantity)
        price = float(service.unit_price) if service else 0
        total = price * 1 
        total_amount += total
        
        result.append({
            'order_id': order.service_order_id,
            'service_name': service.service_name if service else '---',
            'quantity': 1,
            'price': price,
            'total': total,
            'status': order.status,
            'ticket_code': order.ticket_code
        })
        
    return jsonify({
        'success': True, 
        'data': result,
        'total_amount': total_amount
    })

# API LƯU CHỈ ĐỊNH
@kham_benh_bp.route('/api/kham-benh/luu-chi-dinh', methods=['POST'])
def save_service_batch():
    try:
        data = request.json
        exam_id = data.get('exam_id')
        services_input = data.get('services') 
        
        if not exam_id or not services_input:
            return jsonify({'success': False, 'message': 'Dữ liệu không hợp lệ!'}), 400

        # --- CHUẨN BỊ BIẾN ---
        grouped_services = {}      # Gom nhóm để tách phiếu
        total_amount_invoice = 0   # Tổng tiền
        invoice_details_list = []  # List chi tiết hóa đơn
        processed_rooms = set()    # Set để tránh tạo trùng STT phòng
        
        today = datetime.now().date()


        for item in services_input:
            # Xử lý input
            if isinstance(item, dict):
                service_id = int(item.get('service_id'))
                room_id_input = int(item.get('room_id')) if item.get('room_id') else None
                
            else: continue # Bỏ qua nếu data lỗi

            # Truy vấn thông tin dịch vụ
            service_info = db.session.query(Service, CatalogServices)\
                .join(CatalogServices, Service.catalogservice_id == CatalogServices.catalogservice_id)\
                .filter(Service.service_id == service_id).first()
            
            if not service_info: continue
            
            s, cat = service_info
            price = float(s.unit_price)
            cat_name = cat.catalogservice_name.lower()
            # Logic xác định mã nhóm (Prefix cho mã phiếu)
            group_code = 'KHAC'
            if 'xét nghiệm' in cat_name or 'huyết học' in cat_name or 'sinh hóa' in cat_name:
                group_code = 'XN'
            elif 'siêu âm' in cat_name or 'chụp x quang' in cat_name or 'chụp ct' in cat_name or 'nội soi' in cat_name:
                group_code = 'CDHA'
            elif 'phẫu thuật' in cat_name or 'thủ thuật' in cat_name:
                group_code = 'PTTT'
            
            if group_code not in grouped_services:
                grouped_services[group_code] = []
            
            # Thêm vào list nhóm để lát tạo ServiceOrder
            grouped_services[group_code].append({
                'service_id': service_id,
                'room_id': room_id_input
            })

            # 1.2. Cộng dồn hóa đơn
            total_amount_invoice += price
            invoice_details_list.append({
                'service_id': service_id,
                'price': price
            })


        created_tickets = []
        base_time = int(time.time())
        
        for group_code, items in grouped_services.items():
            # Tạo mã phiếu
            ticket_code = f"{group_code}_{base_time}"
            created_tickets.append(ticket_code)
            
            for svc in items:
                # A. Lưu ServiceOrder
                new_order = ServiceOrder(
                    examination_id=exam_id,
                    service_id=svc['service_id'],
                    status='Chưa thực hiện',
                    ticket_code=ticket_code
                )
                db.session.add(new_order)

                # B. Tạo SessionRoom (Xếp hàng tại phòng thực hiện)
                r_id = svc['room_id']
                if r_id and r_id not in processed_rooms:
                    # Kiểm tra đã có số ở phòng này chưa
                    exists = SessionRooms.query.filter_by(examination_id=exam_id, room_id=r_id).first()
                    
                    if not exists:
                        # Tính STT lớn nhất
                        max_stt = db.session.query(func.max(SessionRooms.number_order))\
                            .join(ExaminationSession, SessionRooms.examination_id == ExaminationSession.examination_id)\
                            .filter(SessionRooms.room_id == r_id, func.date(ExaminationSession.create_date) == today)\
                            .scalar()
                        
                        new_stt = 1 if max_stt is None else max_stt + 1
                        
                        # Lấy thông tin BN
                        patient = db.session.query(Patient).join(ExaminationSession).filter(ExaminationSession.examination_id == exam_id).first()
                        age = datetime.now().year - patient.date_birth.year if patient.date_birth else 0

                        # Lưu SessionRoom
                        new_sr = SessionRooms(
                            examination_id=exam_id,
                            room_id=r_id,
                            number_order=new_stt,
                            patient_name=patient.full_name,
                            age=age
                            
                        )
                        db.session.add(new_sr)
                        processed_rooms.add(r_id) # Đánh dấu đã xử lý phòng này


        if total_amount_invoice > 0:
            # Tạo Invoice
            new_invoice = Invoice(
                examination_id=exam_id,
                total_amount=total_amount_invoice,
                status='Chưa thanh toán',
                create_date=datetime.utcnow()
            )
            db.session.add(new_invoice)
            db.session.flush() # Lấy ID

            # Tạo InvoiceDetail
            for detail in invoice_details_list:
                inv_detail = InvoiceDetail(
                    invoice_id=new_invoice.invoice_id,
                    service_id=detail['service_id'],
                    unit_price=detail['price']
                )
                db.session.add(inv_detail)

        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Lưu thành công! Tổng tiền: {total_amount_invoice:,.0f}', 
            'tickets': created_tickets
        })

    except Exception as e:
        db.session.rollback()
        print("Lỗi Lưu:", e)
        return jsonify({'success': False, 'message': 'Lỗi Server: ' + str(e)}), 500


# Cấu hình Tài khoản Ngân hàng của Bệnh viện (Demo)
BANK_ID = "VCB"          # Mã ngân hàng (MB, VCB, ACB...)
ACCOUNT_NO = "1028076656" # Số tài khoản nhận tiền
TEMPLATE = "compact"    # Mẫu tem (compact, qr_only, print)


# API LẤY HÓA ĐƠN CHO KHÁM BỆNH (ĐÃ FIX LỖI)
@kham_benh_bp.route('/api/kham-benh/hoa-don/<int:patient_id>', methods=['GET'])
def kb_get_invoice_info(patient_id):
    try:
        # 1. Lấy phiên khám đang diễn ra gần nhất
        session = ExaminationSession.query.filter(
            ExaminationSession.patient_id == patient_id,
            ExaminationSession.status != 'Đã khám xong' 
        ).order_by(desc(ExaminationSession.create_date)).first()

        if not session:
             return jsonify({'success': False, 'message': 'Không tìm thấy phiên khám đang hoạt động!'})

        # 2. Lấy các hóa đơn unpaid thuộc phiên khám này
        invoices = Invoice.query.filter_by(
            examination_id=session.examination_id,
            status='Chưa thanh toán'
        ).all()

        if not invoices:
            return jsonify({'success': False, 'message': 'Không có dịch vụ cần thanh toán!'})

        # 3. Tổng hợp dữ liệu
        patient = Patient.query.get(patient_id)
        
        # Kiểm tra room có tồn tại không
        room_name = ""
        if session.room_id:
            room = ClinicRoom.query.get(session.room_id)
            if room: room_name = room.room_name
        
        total_amount_all = 0
        all_details = []
        invoice_ids = []

        for inv in invoices:
            invoice_ids.append(inv.invoice_id)
            total_amount_all += float(inv.total_amount)
            
            for d in inv.details:
                service = Service.query.get(d.service_id)
                all_details.append({
                    'service_name': service.service_name if service else 'Dịch vụ',
                    'unit_price': float(d.unit_price),
                    'quantity': 1,
                    'total': float(d.unit_price)
                })

        # 4. Tìm tên Bác sĩ (Xử lý an toàn tránh lỗi Attribute)
        doctor_name = "Chưa phân công"
        # Cách 1: Lấy từ session nếu có cột doctor_id
        if hasattr(session, 'doctor_id') and session.doctor_id:
            doc = Staff.query.get(session.doctor_id)
            if doc: doctor_name = doc.full_name
        
        # Cách 2: Nếu chưa có, lấy theo phòng khám
        if doctor_name == "Chưa phân công" and session.room_id:
            staff = Staff.query.filter_by(room_id=session.room_id).first()
            if staff: doctor_name = staff.full_name
        
        # 5. Thông tin bệnh nhân & QR
        card = MagneticCard.query.filter_by(patient_id=patient.patient_id).first()
        ma_bn = f"BN{card.card_code}" if card else f"P{patient.patient_id}"
        
        # Tính tuổi an toàn
        tuoi = 0
        if patient.date_birth:
            tuoi = datetime.now().year - patient.date_birth.year

        content = f"TT Kham Benh {ma_bn}"
        qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-{TEMPLATE}.png?amount={int(total_amount_all)}&addInfo={content}"

        return jsonify({
            'success': True,
            'data': {
                'invoice_ids': invoice_ids, 
                'ma_bn': ma_bn,
                'ho_ten': patient.full_name,
                'ngay_sinh': patient.date_birth.strftime('%d/%m/%Y') if patient.date_birth else '',
                'gioi_tinh': patient.gender,
                'tuoi': tuoi,
                'phong_kham': room_name,
                'bac_si': doctor_name,
                'trang_thai': 'Chờ thanh toán',
                'qr_url': qr_url,
                'total_amount': total_amount_all,
                'details': all_details
            }
        })

    except Exception as e:
        print("Lỗi API Hóa đơn Khám bệnh:", e) # Xem lỗi chi tiết ở Terminal
        return jsonify({'success': False, 'message': str(e)}), 500
    

@kham_benh_bp.route('/api/kham-benh/thanh-toan', methods=['POST'])
def kb_pay_invoice():
    try:
        data = request.json
        print("DEBUG PAYLOAD:", data) # In dữ liệu nhận được để kiểm tra

        # 1. Lấy danh sách ID
        ids = data.get('invoice_ids')
        if not ids: 
            # Fallback: Nếu client gửi dạng đơn lẻ
            single_id = data.get('invoice_id')
            ids = [single_id] if single_id else []

        # Lọc ID hợp lệ (số nguyên)
        valid_ids = []
        for x in ids:
            try:
                valid_ids.append(int(x))
            except: pass

        if not valid_ids:
            return jsonify({'success': False, 'message': 'Danh sách hóa đơn trống hoặc không hợp lệ!'}), 400

        payment_method = data.get('payment_method', 'cash')
        total_pay = 0
        invoices_to_pay = []

        # 2. Tìm hóa đơn và tính tiền
        for inv_id in valid_ids:
            inv = Invoice.query.get(inv_id)
            if inv:
                # Nếu hóa đơn chưa thanh toán thì mới tính
                if inv.status == 'Chưa thanh toán':
                    total_pay += float(inv.total_amount)
                    invoices_to_pay.append(inv)
                else:
                    print(f"Hóa đơn {inv_id} trạng thái là {inv.status} -> Bỏ qua")
        
        if not invoices_to_pay:
            return jsonify({'success': False, 'message': 'Các hóa đơn này đã được thanh toán rồi!'}), 400

        # 3. Trừ tiền thẻ (Nếu chọn thẻ)
        if payment_method == 'card':
            session = ExaminationSession.query.get(invoices_to_pay[0].examination_id)
            card = MagneticCard.query.filter_by(patient_id=session.patient_id).first()
            
            if not card:
                return jsonify({'success': False, 'message': 'Bệnh nhân chưa có thẻ!'}), 400
            
            current_balance = float(card.balance) if card.balance else 0.0
            if current_balance < total_pay:
                return jsonify({'success': False, 'message': f'Số dư không đủ! (Cần: {total_pay:,.0f}, Có: {current_balance:,.0f})'}), 400
            
            card.balance = current_balance - total_pay
            db.session.add(card)

        # 4. Cập nhật trạng thái
        for inv in invoices_to_pay:
            inv.status = 'Đã thanh toán'
            inv.payment_method = payment_method
            db.session.add(inv)
            
            sess = ExaminationSession.query.get(inv.examination_id)
            if sess.status == 'waiting': 
                sess.status = 'processing'

        db.session.commit()
        return jsonify({'success': True, 'message': 'Thanh toán thành công!'})

    except Exception as e:
        db.session.rollback()
        print("Lỗi Thanh toán:", e)
        return jsonify({'success': False, 'message': 'Lỗi Server: ' + str(e)}), 500

#API LẤY DANH SÁCH THUỐC (Đơn giản hóa)
@kham_benh_bp.route('/api/thuoc/all', methods=['GET'])
def get_all_medicines():
    medicines = Medicine.query.all()
    data = [{
        'id': m.medicine_id,
        'name': m.medicine_name,
        'unit': m.unit
        # Đã bỏ price và stock
    } for m in medicines]
    return jsonify({'success': True, 'data': data})

#API LƯU ĐƠN THUỐC (Theo Model của bạn)
@kham_benh_bp.route('/api/kham-benh/luu-don-thuoc', methods=['POST'])
def save_prescription():
    try:
        data = request.json
        exam_id = data.get('exam_id')
        medicines_input = data.get('medicines')
        doctor_advice = data.get('loi_dan')
        
        if not exam_id or not medicines_input:
            return jsonify({'success': False, 'message': 'Dữ liệu không hợp lệ'}), 400

        # A. Xử lý Bảng Prescription (Header)
        # Kiểm tra xem đã có đơn thuốc cho phiên khám này chưa
        prescription = Prescription.query.filter_by(examination_session_id=exam_id).first()
        
        if not prescription:
            prescription = Prescription(
                examination_session_id=exam_id,
                create_date=datetime.utcnow()
            )
            db.session.add(prescription)
            db.session.flush() # Lấy ID để dùng cho bảng chi tiết
        else:
            # Nếu có rồi thì cập nhật ngày sửa (nếu cần)
            prescription.create_date = datetime.utcnow()

        # B. Xử lý Chi tiết (Detail)
        # Xóa sạch chi tiết cũ để lưu lại danh sách mới (tránh trùng lặp)
        PrescriptionDetail.query.filter_by(prescription_id=prescription.prescription_id).delete()
        
        for item in medicines_input:
            unit = item.get('unit', '') 
            
            # 1. TẠO CHUỖI DOSAGE (HƯỚNG DẪN)
            parts = item.get('cach_dung_them')
            
            # Logic: Nếu có nhập số lượng thì mới thêm vào chuỗi
            if item.get('sang') and int(item.get('sang')) > 0: 
                parts.append(f"Sáng {item.get('sang')} {unit}")
                
            if item.get('trua') and int(item.get('trua')) > 0: 
                parts.append(f"Trưa {item.get('trua')} {unit}")
                
            if item.get('chieu') and int(item.get('chieu')) > 0: 
                parts.append(f"Chiều {item.get('chieu')} {unit}")
                
            if item.get('toi') and int(item.get('toi')) > 0: 
                parts.append(f"Tối {item.get('toi')} {unit}")
            
            # Ghép chuỗi lại: "Uống, Sáng 1 viên, Tối 1 viên"
            dosage_str = ", ".join(parts)
            

            # 2. LẤY TỔNG SỐ LƯỢNG CẤP (Đã tính ở Client)
            total_qty = int(item.get('so_luong', 0))

            # 3. LƯU VÀO DB
            detail = PrescriptionDetail(
                prescription_id=prescription.prescription_id,
                medicine_id=int(item.get('id')),
                
                quantity=total_qty,   # <--- LƯU SỐ LƯỢNG VÀO ĐÂY
                dosage=dosage_str     # <--- LƯU CHUỖI HƯỚNG DẪN
            )
            db.session.add(detail)

        # C. Lưu Lời dặn (Thường lưu vào bảng DiagnosisRecord hoặc cập nhật bảng Exam)
        # Vì bảng Prescription của bạn không có cột note, ta lưu vào DiagnosisRecord
        diagnosis = DiagnosisRecord.query.filter_by(examination_id=exam_id).first()
        if diagnosis:
            diagnosis.doctor_advice = doctor_advice
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Lưu thành công!'})

    except Exception as e:
        db.session.rollback()
        print("Lỗi lưu đơn:", e)
        return jsonify({'success': False, 'message': str(e)}), 500

# API LẤY DANH SÁCH PHÒNG CHỨC NĂNG (ĐỂ ĐỔ VÀO DROPDOWN)
@kham_benh_bp.route('/api/phong/chuc-nang', methods=['GET'])
def get_functional_rooms():
    # Lọc các phòng có function là 'Phòng chức năng'
    # (Lưu ý: Kiểm tra kỹ trong DB cột function bạn lưu là gì, ví dụ 'Functional' hay 'Phòng chức năng')
    rooms = ClinicRoom.query.filter(ClinicRoom.function == 'Phòng chức năng').all()
    
    data = [{'id': r.room_id, 'name': r.room_name} for r in rooms]
    return jsonify({'success': True, 'data': data})

@kham_benh_bp.route('/api/kham-benh/bat-dau-kham', methods=['POST'])
def start_examination_process():
    try:
        data = request.json
        exam_id = data.get('exam_id')
        
        session = ExaminationSession.query.get(exam_id)
        if not session:
            return jsonify({'success': False, 'message': 'Không tìm thấy phiên khám'}), 404

        # Chỉ cập nhật nếu trạng thái hiện tại là 'paid' (Đã đóng tiền/Đợi khám)
        # hoặc 'waiting' (nếu quy trình bên bạn cho phép khám trước trả tiền sau)
        if session.status in ['Chờ khám', 'Tiếp nhận']:
            session.status = 'Đang khám' # Chuyển sang Đang khám
            db.session.commit()
            return jsonify({'success': True, 'message': 'Đã cập nhật trạng thái: Đang khám'})
        
        # Nếu đang là 'processing' hoặc 'done' thì không làm gì, chỉ trả về success
        return jsonify({'success': True, 'message': 'Trạng thái đã được cập nhật trước đó'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500



@kham_benh_bp.route('/api/kham-benh/in-don-thuoc/<int:exam_id>', methods=['GET'])
def print_prescription_data(exam_id):
    try:
        # 1. Lấy thông tin Phiên khám & Bệnh nhân
        session = ExaminationSession.query.get(exam_id)
        if not session:
            return jsonify({'success': False, 'message': 'Không tìm thấy phiên khám'}), 404
            
        patient = Patient.query.get(session.patient_id)
        card = MagneticCard.query.filter_by(patient_id=patient.patient_id).first()
        ma_bn = f"BN{card.card_code}" if card else f"P{patient.patient_id}"

        diag_record = DiagnosisRecord.query.filter_by(examination_id=exam_id).first()
        
        weight = 0
        height = 0
        bmi = 0
        ngay_tai_kham = ""
        doctor_advice = ""
        
        if diag_record:
            weight = diag_record.weight if diag_record.weight else 0
            height = diag_record.height if diag_record.height else 0
            # Tính BMI (Chiều cao đổi ra mét)
            if height > 0 and weight > 0:
                h_m = height / 100
                bmi = round(weight / (h_m * h_m), 1)
            
            # Lấy ngày tái khám
            if diag_record.re_examination_date:
                ngay_tai_kham = diag_record.re_examination_date.strftime("%d/%m/%Y")
            
            # Lấy lời dặn từ record (nếu có)
            doctor_advice = diag_record.doctor_advice

        # Lấy lời dặn từ session nếu record không có (fallback)
        if not doctor_advice and session.doctor_advice:
            doctor_advice = session.doctor_advice


        # 2. Lấy danh sách thuốc (Từ bảng Prescription -> PrescriptionDetail)
        prescription = Prescription.query.filter_by(examination_session_id=exam_id).first()
        medicines_list = []
        
        if prescription:
            details = PrescriptionDetail.query.filter_by(prescription_id=prescription.prescription_id).all()
            for index, d in enumerate(details):
                med = Medicine.query.get(d.medicine_id)
                hoat_chat = getattr(med, 'generic_name', '') or '' # generic_name
                ham_luong = getattr(med, 'strength', '') or ''          # strength
                medicines_list.append({
                    'stt': index + 1,
                    'ten_thuoc': med.medicine_name,
                    'hoat_chat': hoat_chat,       
                    'ham_luong': ham_luong,
                    'dvt': med.unit,
                    'so_luong': d.quantity,
                    'cach_dung': d.dosage # VD: Sáng 1, Chiều 1...
                })
        # 3. Lấy Chẩn đoán & Lời dặn từ bảng ExaminationSession
        
        
        chan_doan = session.diagnosis if session.diagnosis else ""

        # Thông tin bác sĩ
        # 1. Khởi tạo tên mặc định TRƯỚC (Để nếu query lỗi thì vẫn có tên này dùng)
        final_doctor_name = "Bs. Khám bệnh"

        try:
            # 2. Thực hiện truy vấn
            result = db.session.query(Staff, Expertise)\
                .join(ClinicRoom, Staff.room_id == ClinicRoom.room_id)\
                .join(ExaminationSession, ExaminationSession.room_id == ClinicRoom.room_id)\
                .join(Expertise, Staff.expertise_id == Expertise.expertise_id)\
                .filter(
                    ExaminationSession.examination_id == exam_id,
                    ClinicRoom.function == 'Khám bệnh'
                ).first()

            # 3. Kiểm tra và gán dữ liệu (Chỉ làm khi result có dữ liệu)
            if result:
                # Unpack kết quả ngay tại đây
                staff_data, expertise_data = result
                
                # Kiểm tra chắc chắn các object không bị None
                if staff_data and expertise_data:
                    final_doctor_name = f"{expertise_data.expertise_name}. {staff_data.full_name}"
                    
        except Exception as e_doc:
            print(f"Không tìm thấy bác sĩ phòng khám: {e_doc}")
            # Nếu lỗi thì code sẽ tự động dùng giá trị mặc định "Bs. Khám bệnh" đã khai báo ở bước 1

            # 4. Trả về dữ liệu
            data = {
            # ... Các trường khác giữ nguyên ...
            
                'bac_si': final_doctor_name # Tuyệt đối KHÔNG dùng biến staff_data ở đây
            }

            return jsonify({'success': True, 'data': data})

        # 4. Trả về dữ liệu
        data = {
            # --- Thông tin cơ sở (Cứng hoặc lấy từ Config) ---
            'so_y_te': 'SỞ Y TẾ TP. HỒ CHÍ MINH',
            'ten_bv': 'BỆNH VIỆN LKC',
            'dia_chi_bv': '79 Bà Triệu, Xã Hóc Môn, Tp.HCM',
            'sdt_bv': '028.39914.208',
            
            # --- Thông tin phiếu ---
            'ma_don': f"{datetime.now().strftime('%y%m')}/{exam_id:04d}", # VD: 2510/0010
            'ngay_in_ngay': datetime.now().day,
            'ngay_in_thang': datetime.now().month,
            'ngay_in_nam': datetime.now().year,

            # --- Thông tin bệnh nhân ---
            'ma_bn': ma_bn,
            'ho_ten': patient.full_name.upper(),
            'cccd': patient.id_number if patient.id_number else '',
            'ngay_sinh': patient.date_birth.strftime("%d/%m/%Y") if patient.date_birth else '',
            'gioi_tinh': 'Nam' if patient.gender == 'M' else 'Nữ',
            'can_nang': weight,
            'chieu_cao': height,
            'bmi': bmi,
            'dia_chi': patient.address or '',
            'the_bhyt': getattr(patient, 'health_insurance_card', ''), # Nếu model Patient chưa có cột này thì để trống

            # --- Chuyên môn ---
            'chan_doan': chan_doan,
            'loi_dan': doctor_advice,
            'ngay_tai_kham': ngay_tai_kham,
            
            'thuoc': medicines_list,
            'bac_si': final_doctor_name
        }
        return jsonify({'success': True, 'data': data})

    except Exception as e:
        print("Lỗi In đơn:", e)
        return jsonify({'success': False, 'message': str(e)}), 500
    
@kham_benh_bp.route('/api/kham-benh/ket-thuc', methods=['POST'])
def finish_examination():
    try:
        data = request.json
        exam_id = data.get('exam_id')
        
        if not exam_id:
            return jsonify({'success': False, 'message': 'Thiếu ID phiên khám'}), 400

        # 1. Tìm phiên khám
        session = ExaminationSession.query.get(exam_id)
        if not session:
            return jsonify({'success': False, 'message': 'Không tìm thấy phiên khám'}), 404

        # 2. Cập nhật trạng thái Phiên khám
        session.status = 'Hoàn thành' 
        
        # 3. Cập nhật trạng thái trong hàng đợi (SessionRooms)
        session_rooms = SessionRooms.query.filter_by(
            examination_id=exam_id
        ).all()
        
        for sr in session_rooms:
            sr.status = 'Hoàn thành'

        # Lưu thay đổi vào DB
        db.session.commit()

        # --- BẮT ĐẦU DEBUG THÔNG BÁO ---
        print(">>> [DEBUG] Bắt đầu quy trình gửi thông báo...")
        try:
            # 1. Check Session
            print(f">>> [DEBUG] Exam ID: {exam_id}, Patient ID: {session.patient_id}")
            
            patient = Patient.query.get(session.patient_id)
            
            # 2. Check Patient
            if not patient:
                print(">>> [DEBUG] LỖI: Không tìm thấy bệnh nhân trong DB!")
            else:
                print(f">>> [DEBUG] Bệnh nhân: {patient.full_name}, Account ID: {patient.account_id}")

                # 3. Check Account ID
                if not patient.account_id:
                    print(">>> [DEBUG] CẢNH BÁO: Bệnh nhân này chưa liên kết tài khoản (account_id is Null). Không gửi thông báo.")
                else:
                    # 4. Gửi
                    print(f">>> [DEBUG] Đang bắn Socket tới Room: user_{patient.account_id}")
                    send_notification(
                        account_id=patient.account_id,
                        type_notif='complete',
                        title='Hoàn thành khám bệnh',
                        message=f'Bạn đã hoàn thành buổi khám. Vui lòng kiểm tra đơn thuốc.'
                    )
                    print(">>> [DEBUG] Đã gọi hàm send_notification thành công.")

        except Exception as e_notify:
            print(f">>> [DEBUG] EXCEPTION khi gửi thông báo: {e_notify}")
        # --- KẾT THÚC DEBUG ---

        return jsonify({'success': True, 'message': 'Đã kết thúc phiên khám!'})

    except Exception as e:
        db.session.rollback()
        print("Lỗi kết thúc khám:", e)
        return jsonify({'success': False, 'message': str(e)}), 500