from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models import (
    Patient, ClinicRoom, Service, CatalogServices, ExaminationSession, 
    Account, MagneticCard, Invoice, InvoiceDetail, SessionRooms, Staff
)
from datetime import datetime, date
from sqlalchemy import func
from sqlalchemy import desc, or_
from werkzeug.security import generate_password_hash

from app.decorators import role_required

tiep_don_bp = Blueprint('tiep_don', __name__)

# --- 1. ROUTE HIỂN THỊ GIAO DIỆN (GET) ---
@tiep_don_bp.route('/quan-ly-tiep-don')
@role_required(['Admin', 'Lễ tân'])
def show_tiep_don():
    # Lấy dữ liệu danh mục để đổ vào dropdown
    rooms = ClinicRoom.query.all()
    catalogs = CatalogServices.query.all()
    
    # Lấy tất cả dịch vụ, nhưng sẽ group hoặc filter ở frontend
    services = Service.query.all()
    
    return render_template('kham_benh/tiep_don.html', 
                           rooms=rooms, 
                           catalogs=catalogs, 
                           services=services)

# --- API: LẤY THÔNG TIN TỪ MÃ THẺ (Khi quẹt thẻ) ---
@tiep_don_bp.route('/api/patient-info/<card_code>', methods=['GET'])
@role_required(['Admin', 'Lễ tân'])
def get_patient_by_card(card_code):
    # Tìm thẻ trong DB
    card = MagneticCard.query.filter_by(card_code=card_code).first()
    
    if card and card.patient_ref:
        # Nếu thẻ đã tồn tại và đã liên kết bệnh nhân
        p = card.patient_ref
        card_info = {
            'card_code': card.card_code,
            'create_date': card.create_date.strftime('%d/%m/%Y') if card.create_date else '',
            'status': card.status,
            'balance': float(card.balance) if card.balance else 0
        }
        return jsonify({
            'found': True,
            'full_name': p.full_name,
            'gender': p.gender,
            'dob': p.date_birth.strftime('%d/%m/%Y') if p.date_birth else '',
            'phone': p.phone,
            'address': p.address,
            'cccd': p.id_number,
            'card_data': card_info
        })
    else:
        # Thẻ chưa tồn tại hoặc chưa có thông tin (Khách mới)
        return jsonify({
            'found': False,
            'message': 'Thẻ mới chưa có dữ liệu bệnh nhân'
        })

# --- 2. ROUTE XỬ LÝ LƯU (POST) ---
@tiep_don_bp.route('/api/tiep-don/luu', methods=['POST'])
@role_required(['Admin', 'Lễ tân'])
def save_reception():
    try:
        data = request.json
        card_code = data.get('ma_the') # Mã thẻ từ input
        room_id = data.get('phong_kham_id')
        service_id = data.get('dich_vu_id')

        if not card_code:
            return jsonify({'success': False, 'message': 'Vui lòng quẹt thẻ hoặc nhập mã thẻ!'}), 400

        room_id = int(room_id)
        service_id = int(service_id)

        # Bắt đầu Transaction
        # ---------------------------------------------------------
        
        # BƯỚC 7: KIỂM TRA MÃ THẺ & XỬ LÝ BỆNH NHÂN/ACCOUNT
        card = MagneticCard.query.filter_by(card_code=card_code).first()
        patient = None

        if card:
            # --- TRƯỜNG HỢP CÓ THẺ: CẬP NHẬT THÔNG TIN ---
            patient = card.patient_ref
            if not patient: 
              
                patient = Patient()
                patient.card_id = card.card_id
                db.session.add(patient)
            
            # Cập nhật thông tin từ form
            patient.full_name = data.get('ho_ten')
            patient.gender = data.get('gioi_tinh')
            patient.phone = data.get('sdt')
            patient.address = data.get('dia_chi')
            patient.id_number = data.get('cccd')
            if data.get('ngay_sinh'):
                patient.date_birth = datetime.strptime(data.get('ngay_sinh'), '%d/%m/%Y').date()
            
            
        else:
            # --- TRƯỜNG HỢP CHƯA CÓ THẺ: TẠO MỚI TOÀN BỘ ---
            
            # A. Tạo Account (Mặc định user = mã thẻ, pass = 123456)
            new_account = Account(
                username=card_code,
                email=f"{card_code}@gmail.com",
                password=generate_password_hash("123456"),
                role_id=5 
            )
            db.session.add(new_account)
            db.session.flush() # Để lấy account_id

            # B. Tạo Patient
            patient = Patient(
                full_name=data.get('ho_ten'),
                gender=data.get('gioi_tinh'),
                phone=data.get('sdt'),
                address=data.get('dia_chi'),
                id_number=data.get('cccd'),
                account_id=new_account.account_id
            )
            if data.get('ngay_sinh'):
                patient.date_birth = datetime.strptime(data.get('ngay_sinh'), '%d/%m/%Y').date()
            
            db.session.add(patient)
            db.session.flush() # Để lấy patient_id

            # C. Tạo MagneticCard
            new_card = MagneticCard(
                card_code=card_code,
                patient_id=patient.patient_id,
                status='Đang hoạt động',
                balance=0
            )
            db.session.add(new_card)
            db.session.flush()

            # Update ngược lại card_id cho patient (vì quan hệ vòng)
            patient.card_id = new_card.card_id

        # BƯỚC 9: TẠO EXAMINATION SESSION & HÓA ĐƠN
        
        # A. Tạo Phiên khám
        session = ExaminationSession(
            patient_id=patient.patient_id,
            room_id=room_id,
            reason=data.get('ly_do_kham'),
            status='Tiếp nhận',
            create_date=datetime.utcnow()
        )
        db.session.add(session)
        db.session.flush() # Lấy session.examination_id

        
        # BƯỚC 8: TẠO SỐ THỨ TỰ TRONG SESSION ROOMS
        today = datetime.now().date()
        # 1. Tính tuổi
        age = 0
        if patient.date_birth:
            age = date.today().year - patient.date_birth.year

        # 2. Tính số thứ tự (Max số thứ tự hiện tại của phòng đó + 1)
        # Chỉ đếm những người đang chờ (waiting) hoặc đang khám (processing)
        max_stt = db.session.query(func.max(SessionRooms.number_order))\
            .join(ExaminationSession, SessionRooms.examination_id == ExaminationSession.examination_id)\
            .filter(
                SessionRooms.room_id == room_id,
                func.date(ExaminationSession.create_date) == today
            ).scalar()
        new_order = 1 if max_stt is None else max_stt + 1

        # 3. Lưu vào bảng SessionRooms
        session_room = SessionRooms(
            examination_id=session.examination_id,
            room_id=room_id,
            number_order=new_order,
            patient_name=patient.full_name,
            age=age,
            status = 'Đang chờ'
        )
        db.session.add(session_room)

        # BƯỚC 9B: TẠO HÓA ĐƠN & CHI TIẾT (INVOICE)
        # Tìm dịch vụ để lấy đơn giá
        service_obj = Service.query.get(service_id)
        
        if service_obj:
            # 1. Tạo Hóa đơn tổng (Invoice)
            invoice = Invoice(
                examination_id=session.examination_id,
                total_amount=service_obj.unit_price, # Tổng tiền = tiền dịch vụ khám
                status='Chưa thanh toán',
                payment_method='Thẻ', # Mặc định
                create_date=datetime.utcnow()
            )
            db.session.add(invoice)
            db.session.flush() # Lấy invoice_id

            # 2. Tạo Chi tiết hóa đơn (InvoiceDetail)
            inv_detail = InvoiceDetail(
                invoice_id=invoice.invoice_id,
                service_id=service_obj.service_id,
                unit_price=service_obj.unit_price
            )
            db.session.add(inv_detail)
        else:
            # Nếu không tìm thấy dịch vụ thì rollback và báo lỗi
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Dịch vụ không tồn tại trong CSDL!'}), 400

        # ---------------------------------------------------------
        # COMMIT TẤT CẢ (LƯU VÀO DB)
        # ---------------------------------------------------------
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Đăng ký thành công!',
            'stt': new_order,
            'patient_name': patient.full_name,
            'room_id': room_id,
            'invoice_id': invoice.invoice_id
        })

    except Exception as e:
        db.session.rollback() # Hoàn tác nếu lỗi
        print(e)
        return jsonify({'success': False, 'message': 'Lỗi hệ thống: ' + str(e)}), 500


#  Route Danh dách tiếp nhận
@tiep_don_bp.route('/api/tiep-don/danh-sach', methods=['GET'])
@role_required(['Admin', 'Lễ tân'])
def get_reception_list():
    try:
        
        keyword = request.args.get('keyword', '').strip()
        date_range = request.args.get('date', '')
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Cố định 10 dòng/trang
        query = db.session.query(ExaminationSession)\
            .join(Patient)\
            .outerjoin(MagneticCard, MagneticCard.patient_id == Patient.patient_id)

        # 3. XỬ LÝ TÌM KIẾM THEO TỪ KHÓA (Tên hoặc Mã BN)
        if keyword:
            
            clean_keyword = keyword.upper().replace("BN", "")
            
            search_condition = or_(
                Patient.full_name.ilike(f"%{keyword}%"),       # Tìm theo tên (không phân biệt hoa thường)
                MagneticCard.card_code.like(f"%{clean_keyword}%"), # Tìm theo mã thẻ
                Patient.phone.like(f"%{keyword}%")             # Tìm theo SĐT (khuyến mãi thêm)
            )
            query = query.filter(search_condition)

        # 4. XỬ LÝ LỌC THEO NGÀY (dd/mm/yyyy - dd/mm/yyyy)
        if date_range and date_range.strip():
            try:
                
                input_date = datetime.strptime(date_range.strip(), '%d/%m/%Y')
                
                start_time = input_date
                
                end_time = input_date.replace(hour=23, minute=59, second=59)
                
                query = query.filter(ExaminationSession.create_date.between(start_time, end_time))
            except ValueError:
                pass 
        # 3. THỰC HIỆN PHÂN TRANG (Thay thế đoạn .limit(50).all() cũ)
        # Sắp xếp mới nhất lên đầu
        query = query.order_by(desc(ExaminationSession.create_date))
        
        # Dùng hàm paginate của Flask-SQLAlchemy
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        sessions = pagination.items  # Danh sách 10 bản ghi của trang hiện tại
        
        # 6. FORMAT DỮ LIỆU TRẢ VỀ (Giống code cũ)
        result = []
        for index, sess in enumerate(sessions):
            patient = sess.patient
            
            stt_real = (page - 1) * per_page + (index + 1)
            # Xử lý Mã BN
            card = MagneticCard.query.filter_by(patient_id=patient.patient_id).first()
            display_ma_bn = f"BN{card.card_code}" if card else f"P{patient.patient_id:06d}"

            # Xử lý trạng thái
            status_map = {
                'Tiếp nhận': '<span class="badge bg-info">Tiếp nhận</span>',
                'Chờ khám': '<span class="badge bg-primary">Chờ khám</span>',
                'Đang khám': '<span class="badge bg-warning">Đang khám</span>',
                'Hoàn thành': '<span class="badge bg-success">Hoàn thành</span>'
            }
            status_html = status_map.get(sess.status, sess.status)

            row = {
                'id': sess.examination_id,
                'stt': stt_real,
                'ma_bn': display_ma_bn,
                'patient_id': patient.patient_id,
                'ho_ten': patient.full_name,
                'ma_dk_kham': f"DK{sess.examination_id:09d}",
                'thoi_gian': sess.create_date.strftime('%d/%m/%Y %H:%M:%S'),
                'gioi_tinh': patient.gender or '',
                'ngay_sinh': patient.date_birth.strftime('%d/%m/%Y') if patient.date_birth else '',
                'sdt': patient.phone or '',
                'trang_thai': status_html
            }
            result.append(row)

        return jsonify({
            'success': True,
            'data': result,
            'pagination': {
                'current_page': page,
                'total_pages': pagination.pages,
                'total_items': pagination.total,
                'per_page': per_page
            }
        })

    except Exception as e:
        print("Lỗi:", e)
        return jsonify({'success': False, 'message': str(e)}), 500
    
@tiep_don_bp.route('/api/tiep-don/xoa', methods=['POST'])
@role_required(['Admin', 'Lễ tân'])
def delete_reception():
    try:
        data = request.json
        exam_id = data.get('id')
        
        # 1. Tìm phiên khám
        session = ExaminationSession.query.get(exam_id)
        
        if not session:
            return jsonify({'success': False, 'message': 'Không tìm thấy phiếu khám!'}), 404

        # 2. KIỂM TRA ĐIỀU KIỆN: Chỉ được xóa "waiting"
        # Map trạng thái sang tiếng Việt để thông báo cho thân thiện
        status_map = {
            'processing': 'Đang khám',
            'done': 'Đã khám',
            'unpaid': 'Chưa đóng tiền'
        }
        
        if session.status != 'Tiếp nhận':
            status_vn = status_map.get(session.status, session.status)
            return jsonify({
                'success': False, 
                'message': f'Không thể xóa! Trạng thái hiện tại là "{status_vn}".'
            }), 400

        # 3. THỰC HIỆN XÓA (Xóa các bảng liên quan trước)
        
        # A. Xóa trong danh sách chờ phòng khám (SessionRooms)
        SessionRooms.query.filter_by(examination_id=exam_id).delete()
        
        # B. Xóa chi tiết hóa đơn & Hóa đơn (Nếu chưa thanh toán)
        invoices = Invoice.query.filter_by(examination_id=exam_id).all()
        for inv in invoices:
            # Xóa chi tiết trước
            InvoiceDetail.query.filter_by(invoice_id=inv.invoice_id).delete()
            # Xóa hóa đơn sau
            db.session.delete(inv)
            
        # C. Xóa phiếu khám (ExaminationSession)
        db.session.delete(session)
        
        # 4. Lưu thay đổi
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Đã xóa phiếu khám thành công!'})

    except Exception as e:
        db.session.rollback()
        print("Lỗi xóa:", e)
        return jsonify({'success': False, 'message': 'Lỗi hệ thống: ' + str(e)}), 500

# ROUTE LẤY THÔNG TIN TÀI KHOẢN
@tiep_don_bp.route('/api/tiep-don/tai-khoan/<int:patient_id>', methods=['GET'])
def get_account_info(patient_id):
    try:
        # Query thông tin
        patient = Patient.query.get(patient_id)
        if not patient:
            return jsonify({'success': False, 'message': 'Không tìm thấy bệnh nhân'}), 404
            
        account = Account.query.get(patient.account_id)
        card = MagneticCard.query.filter_by(patient_id=patient_id).first()
        
        # Mật khẩu hiển thị (Vì đã hash nên không lấy lại được pass cũ)
        # Ta giả định mật khẩu mặc định khởi tạo là 123456 để in ra phiếu
        real_password_for_print = "123456" 

        return jsonify({
            'success': True,
            'data': {
                'patient_id': patient.patient_id,
                'ma_bn': f"BN{card.card_code}" if card else f"P{patient.patient_id}",
                'ho_ten': patient.full_name,
                'gioi_tinh': patient.gender,
                'ngay_sinh': patient.date_birth.strftime('%d/%m/%Y') if patient.date_birth else '',
                'sdt': patient.phone,
                'cccd': patient.id_number,
                'dia_chi': patient.address,
                'nguoi_nha': patient.description,

                'account_id': account.account_id if account else None,
                'username': account.username if account else "Chưa có",
                'email': account.email if account else '',
                # Trả về hash để hiển thị chứng minh bảo mật
                'password_hash': account.password[:20] + "..." if account else "", 
                # Trả về pass mặc định để in phiếu
                'password_print': real_password_for_print,

                'card_id': card.card_id if card else None,
                'ma_the': card.card_code if card else "Chưa cấp thẻ",
                'balance': float(card.balance) if card else 0,
                'card_status': card.status if card else 'Chưa có',
                'card_created': card.create_date.strftime('%d/%m/%Y') if card and card.create_date else ''
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 2. [MỚI] API NẠP TIỀN
@tiep_don_bp.route('/api/tiep-don/nap-tien', methods=['POST'])
def deposit_money():
    try:
        data = request.json
        patient_id = data.get('patient_id')
        amount = float(data.get('amount'))

        # Tìm thẻ của bệnh nhân
        card = MagneticCard.query.filter_by(patient_id=patient_id).first()
        
        if not card:
            # Nếu chưa có thẻ, tạo thẻ ảo để lưu tiền (Tùy logic bệnh viện)
            # Ở đây ta báo lỗi bắt buộc phải có thẻ
            return jsonify({'success': False, 'message': 'Bệnh nhân này chưa có thẻ từ!'}), 400

        # Cộng tiền
        current_balance = float(card.balance) if card.balance else 0.0
        new_balance = current_balance + amount
        card.balance = new_balance
        
        # (Tùy chọn) Nên lưu lịch sử giao dịch vào bảng TransactionLogs nếu có
        
        db.session.commit()

        # Format tiền việt nam
        new_balance_fmt = "{:,.0f}".format(new_balance).replace(",", ".")

        return jsonify({
            'success': True, 
            'new_balance': new_balance,
            'new_balance_formatted': new_balance_fmt
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
# 2. [MỚI] API CẬP NHẬT THÔNG TIN (SỬA)
@tiep_don_bp.route('/api/tiep-don/cap-nhat-benh-nhan', methods=['POST'])
def update_patient_info():
    try:
        data = request.json
        p_id = data.get('patient_id')
        
        patient = Patient.query.get(p_id)
        if not patient:
            return jsonify({'success': False, 'message': 'Lỗi ID bệnh nhân'}), 404

        # A. Cập nhật bảng Patient
        patient.full_name = data.get('ho_ten')
        patient.gender = data.get('gioi_tinh')
        patient.phone = data.get('sdt')
        patient.id_number = data.get('cccd')
        patient.address = data.get('dia_chi')
        patient.description = data.get('nguoi_nha')
        
        if data.get('ngay_sinh'):
            patient.date_birth = datetime.strptime(data.get('ngay_sinh'), '%d/%m/%Y').date()

        # B. Cập nhật bảng Account (Email)
        if patient.account_id:
            acc = Account.query.get(patient.account_id)
            if acc:
                acc.email = data.get('email')

        # C. Cập nhật bảng Card (Trạng thái)
        if patient.card_id:
            card = MagneticCard.query.get(patient.card_id)
            if card:
                card.status = data.get('card_status')

        db.session.commit()
        return jsonify({'success': True, 'message': 'Cập nhật thông tin thành công!'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# 3. [MỚI] API XÓA BỆNH NHÂN (XÓA GỐC)
@tiep_don_bp.route('/api/tiep-don/xoa-benh-nhan', methods=['POST'])
def delete_patient_full():

    try:
        p_id = request.json.get('patient_id')
        
        # Kiểm tra ràng buộc: Nếu đã khám (có ExaminationSession) thì KHÔNG được xóa gốc
        # Chỉ cho phép xóa nếu là hồ sơ rác hoặc vừa tạo nhầm
        has_exam = ExaminationSession.query.filter_by(patient_id=p_id).first()
        if has_exam:
            return jsonify({'success': False, 'message': 'Không thể xóa! Bệnh nhân này đã có lịch sử khám bệnh.'}), 400

        patient = Patient.query.get(p_id)
        if patient:
            # Xóa Thẻ trước
            MagneticCard.query.filter_by(patient_id=p_id).delete()
            
            # Xóa Account sau
            acc_id = patient.account_id
            
            # Xóa Patient
            db.session.delete(patient)
            
            # Xóa Account cuối cùng
            if acc_id:
                Account.query.filter_by(account_id=acc_id).delete()
                
            db.session.commit()
            return jsonify({'success': True, 'message': 'Đã xóa hồ sơ bệnh nhân vĩnh viễn!'})
        
        return jsonify({'success': False, 'message': 'Không tìm thấy hồ sơ'}), 404

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Cấu hình Tài khoản Ngân hàng của Bệnh viện (Demo)
BANK_ID = "VCB"          # Mã ngân hàng (MB, VCB, ACB...)
ACCOUNT_NO = "1028076656" # Số tài khoản nhận tiền
TEMPLATE = "compact"    # Mẫu tem (compact, qr_only, print)

@tiep_don_bp.route('/api/tiep-don/hoa-don/<int:patient_id>', methods=['GET'])
def get_invoice_info(patient_id):
    try:
        # 1. Tìm hóa đơn chưa thanh toán
        invoice = db.session.query(Invoice).join(ExaminationSession).filter(
            ExaminationSession.patient_id == patient_id,
            Invoice.status == 'Chưa thanh toán'
        ).order_by(desc(Invoice.create_date)).first()

        if not invoice:
            return jsonify({'success': False, 'message': 'Không có hóa đơn cần thanh toán!'})

        # 2. Lấy thông tin liên quan
        patient = Patient.query.get(patient_id)
        session = ExaminationSession.query.get(invoice.examination_id)
        room = ClinicRoom.query.get(session.room_id)
        
        # Tìm Bác sĩ phụ trách phòng này (Lấy người đầu tiên tìm thấy)
        doctor = Staff.query.filter_by(room_id=room.room_id).first()
        doctor_name = doctor.full_name if doctor else "Chưa phân công"

        # [MỚI] Truy vấn lấy Số thứ tự từ bảng SessionRooms
        session_room = SessionRooms.query.filter_by(examination_id=session.examination_id).first()
        stt_kham = session_room.number_order if session_room else 0

        # 3. Tạo link QR Code (VietQR API)
        # Format: https://img.vietqr.io/image/<BANK_ID>-<ACCOUNT_NO>-<TEMPLATE>.png?amount=<AMOUNT>&addInfo=<CONTENT>
        content = f"Thanh toan HD {invoice.invoice_id} BN{patient.linked_card[0].card_code}" if patient.linked_card else f"P{patient.patient_id}"
        amount = int(invoice.total_amount)
        qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-{TEMPLATE}.png?amount={amount}&addInfo={content}"

        # 4. Map trạng thái phiên khám
        status_map = {
            'waiting': 'Chờ khám',
            'processing': 'Đang khám',
            'done': 'Hoàn thành',
            'unpaid': 'Chờ đóng tiền'
        }
        status_vn = status_map.get(session.status, session.status)

        # 5. Lấy chi tiết dịch vụ
        details = []
        for d in invoice.details:
            service = Service.query.get(d.service_id)
            details.append({
                'id': d.invoice_detail_id, # ID chi tiết để xử lý logic
                'service_name': service.service_name if service else 'Dịch vụ cũ',
                'unit_price': float(d.unit_price),
                'quantity': 1, 
                'total': float(d.unit_price)
            })

        return jsonify({
            'success': True,
            'data': {
                'invoice_id': invoice.invoice_id,
                'ma_bn': f"BN{patient.linked_card[0].card_code}" if patient.linked_card else f"P{patient.patient_id}",
                'ho_ten': patient.full_name,
                'ngay_sinh': patient.date_birth.strftime('%d/%m/%Y') if patient.date_birth else '',
                'gioi_tinh': patient.gender,
                'tuoi': (date.today().year - patient.date_birth.year) if patient.date_birth else 0,
                
                'stt': stt_kham,
                'phong_kham_ten': room.room_name if room else "",
                
                # Thông tin mới thêm
                'phong_kham': f"{room.room_number} - {room.room_name}" if room else "",
                'bac_si': doctor_name,
                'trang_thai': status_vn,
                'qr_url': qr_url,
                
                'total_amount': float(invoice.total_amount),
                'details': details
            }
        })

    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)}), 500


# 2. API THỰC HIỆN THANH TOÁN
@tiep_don_bp.route('/api/tiep-don/thanh-toan', methods=['POST'])
def pay_invoice():
    try:
        data = request.json
        invoice_id = data.get('invoice_id')
        payment_method = data.get('payment_method') # 'cash' hoặc 'card'
        
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'success': False, 'message': 'Hóa đơn không tồn tại'}), 404

        # Nếu thanh toán bằng thẻ -> Trừ tiền
        if payment_method == 'card':
            session = ExaminationSession.query.get(invoice.examination_id)
            patient_id = session.patient_id
            card = MagneticCard.query.filter_by(patient_id=patient_id).first()
            
            if not card:
                return jsonify({'success': False, 'message': 'Bệnh nhân không có thẻ để thanh toán!'}), 400
            
            if card.balance < invoice.total_amount:
                return jsonify({'success': False, 'message': 'Số dư trong thẻ không đủ!'}), 400
            
            # Trừ tiền
            card.balance -= invoice.total_amount
            db.session.add(card)

        # Cập nhật trạng thái hóa đơn
        invoice.status = 'Đã thanh toán'
        invoice.payment_method = payment_method
        db.session.add(invoice)
        
        session = ExaminationSession.query.get(invoice.examination_id)
        if session:
            session.status = 'Chờ khám'
            db.session.add(session)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Thanh toán thành công!'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500