from datetime import date, datetime
from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models import InvoiceDetail, MagneticCard, Patient, Invoice, ExaminationSession, Service, Appointment, SessionRooms, ClinicRoom, get_vn_time

# Tạo Blueprint riêng cho Kiosk
kiosk_bp = Blueprint('kiosk', __name__)

# 1. GIAO DIỆN KIOSK (HTML)
@kiosk_bp.route('/kiosk/thanh-toan')
def kiosk_screen():
    # Render file HTML nằm trong thư mục templates/kiosk/
    return render_template('kiosk/man_hinh_cho.html')

# Cấu hình Ngân hàng (Demo MB Bank)
BANK_ID = "VCB"          # Mã ngân hàng (MB, VCB, ACB...)
ACCOUNT_NO = "1028076656" # Số tài khoản nhận tiền
TEMPLATE = "compact"    # Mẫu tem (compact, qr_only, print)

# 2. API XỬ LÝ THANH TOÁN (BACKEND)
@kiosk_bp.route('/api/kiosk/xu-ly-thanh-toan', methods=['POST'])
def kiosk_process_payment():
    try:
        card_code = request.json.get('card_code')
        
        # A. Tìm thẻ
        card = MagneticCard.query.filter_by(card_code=card_code).first()
        if not card:
            return jsonify({'success': False, 'message': 'Thẻ không hợp lệ hoặc không tồn tại'}), 404

        # B. Tìm bệnh nhân
        patient = Patient.query.get(card.patient_id)
        
        
        # C. Tìm hóa đơn nợ (Unpaid)
        # Join Invoice -> Session để lọc theo patient_id
        invoices = db.session.query(Invoice).join(ExaminationSession).filter(
            ExaminationSession.patient_id == patient.patient_id,
            Invoice.status == 'Chưa thanh toán'
        ).all()

        if not invoices:
            return jsonify({'success': False, 'message': f'Bệnh nhân {patient.full_name} không có hóa đơn cần thanh toán.'}), 400

        # D. Tính toán
        total_pay = sum(float(inv.total_amount) for inv in invoices)
        current_balance = float(card.balance)
        
        # E. Kiểm tra số dư
        if current_balance < total_pay:
             missing_amount = total_pay - current_balance
             
             # Tạo nội dung chuyển khoản: "NAP TIEN [Mã Thẻ]"
             content = f"NAP TIEN {card.card_code}"
             
             # Tạo link VietQR động với số tiền CÒN THIẾU
             qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact.png?amount={int(missing_amount)}&addInfo={content}"
             
             return jsonify({
                'success': False,
                'code': 'LOW_BALANCE', # Mã nhận diện đặc biệt
                'message': 'Số dư không đủ',
                'print_data': {
                    'title': 'YÊU CẦU NẠP TIỀN',
                    'ma_bn': f"BN{card.card_code}",
                    'ho_ten': patient.full_name,
                    'so_du': current_balance,
                    'tong_tien': total_pay,
                    'can_nap': missing_amount, # Số tiền cần nạp thêm
                    'qr_url': qr_url
                }
            })

        # F. Trừ tiền & Cập nhật
        card.balance = current_balance - total_pay
        
        # Lấy tên dịch vụ để in phiếu
        service_names = []
        
        for inv in invoices:
            inv.status = 'Đã thanh toán'
            inv.payment_method = 'card' # Ghi nhận là thanh toán thẻ
            db.session.add(inv)
            
            for d in inv.details:
                s = Service.query.get(d.service_id)
                if s: service_names.append({'name': s.service_name})

            # 2. [QUAN TRỌNG] CẬP NHẬT TRẠNG THÁI PHIÊN KHÁM -> CHỜ KHÁM
            sess = ExaminationSession.query.get(inv.examination_id)
            if sess:
                # Chuyển sang 'processing' để bác sĩ thấy tên bệnh nhân trong danh sách
                sess.status = 'Chờ khám' 
                db.session.add(sess)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Thanh toán thành công',
            'print_data': {
                'ma_bn': f"BN{card.card_code}",
                'ho_ten': patient.full_name,
                'services': service_names,
                'total': total_pay,
                'balance_left': card.balance
            }
        })

    except Exception as e:
        db.session.rollback()
        print("Lỗi Kiosk:", e)
        return jsonify({'success': False, 'message': 'Lỗi hệ thống: ' + str(e)}), 500



@kiosk_bp.route('/api/kiosk/xu-ly-quet-the', methods=['POST'])
def kiosk_process_scan():
    try:
        card_code = request.json.get('card_code')
        
        # A. Tìm thẻ & Bệnh nhân
        card = MagneticCard.query.filter_by(card_code=card_code).first()
        if not card:
            return jsonify({'success': False, 'message': 'Thẻ không hợp lệ'}), 404

        patient = Patient.query.get(card.patient_id)
        if not patient:
            return jsonify({'success': False, 'message': 'Không tìm thấy dữ liệu bệnh nhân'}), 404

        # ============================================================
        # B. ƯU TIÊN 1: KIỂM TRA LỊCH HẸN HÔM NAY (CHECK-IN)
        # ============================================================
        today = date.today()
        
        
        appointment = Appointment.query.filter(
            Appointment.patient_id == patient.patient_id,
            db.func.date(Appointment.appointment_time) == today,
            Appointment.status == 'Chờ xác nhận'
        ).first()

        if appointment:
            # --- LOGIC ĐĂNG KÝ KHÁM TỰ ĐỘNG ---
            
            # 1. Tạo Phiên khám (ExaminationSession)
            new_session = ExaminationSession(
                patient_id=patient.patient_id,
                appointment_id=appointment.appointment_id,
                room_id=appointment.room_id,
                create_date=get_vn_time(),
                reason = appointment.reason,
                status='Tiếp nhận'
            )
            db.session.add(new_session)
            db.session.flush() # Lấy ID

            # 2. Tính số thứ tự (STT) tại phòng đó
            count = SessionRooms.query.filter(
                SessionRooms.room_id == appointment.room_id,
                SessionRooms.create_date == today
            ).count()
            new_stt = count + 1

            # 3. Đưa vào hàng đợi (SessionRooms)
            new_queue = SessionRooms(
                examination_id=new_session.examination_id,
                room_id=appointment.room_id,
                number_order=new_stt,
                patient_name=patient.full_name,
                status='Đang chờ',
                create_date=today
            )
            db.session.add(new_queue)
            service_id = 37
            service_obj = Service.query.get(service_id)
            if service_obj:
            # 1. Tạo Hóa đơn tổng (Invoice)
                invoice = Invoice(
                    examination_id=new_session.examination_id,
                    total_amount=service_obj.unit_price, # Tổng tiền = tiền dịch vụ khám
                    status='Chưa thanh toán',
                    create_date=get_vn_time()
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
            

            # 4. Cập nhật lịch hẹn -> Đã đến
            appointment.status = 'Đã đăng kí'
            
            db.session.commit()

            # Lấy tên phòng
            room = ClinicRoom.query.get(appointment.room_id)
            room_name = room.room_name if room else "Phòng khám"

            return jsonify({
                'success': True,
                'type': 'CHECK_IN', # Đánh dấu loại phản hồi
                'message': 'Check-in thành công',
                'print_data': {
                    'title': 'PHIẾU SỐ THỨ TỰ',
                    'ma_bn': f"BN{card.card_code}",
                    'ho_ten': patient.full_name,
                    'stt': new_stt,          # Số to đùng
                    'phong': room_name,      # Tên phòng
                    'gio_hen': appointment.appointment_time.strftime('%H:%M'),
                    'ghi_chu': 'Vui lòng đến trước cửa phòng khám'
                }
            })

        # ============================================================
        # C. ƯU TIÊN 2: KIỂM TRA THANH TOÁN
        # ============================================================
        invoices = db.session.query(Invoice).join(ExaminationSession).filter(
            ExaminationSession.patient_id == patient.patient_id,
            Invoice.status == 'Chưa thanh toán'
        ).all()

        if invoices:
            # D. Tính toán
            total_pay = sum(float(inv.total_amount) for inv in invoices)
            current_balance = float(card.balance)
        
            # E. Kiểm tra số dư
            if current_balance < total_pay:
                missing_amount = total_pay - current_balance
             
                # Tạo nội dung chuyển khoản: "NAP TIEN [Mã Thẻ]"
                content = f"NAP TIEN {card.card_code}"
             
                # Tạo link VietQR động với số tiền CÒN THIẾU
                qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact.png?amount={int(missing_amount)}&addInfo={content}"
             
                return jsonify({
                    'success': False,
                    'code': 'LOW_BALANCE', # Mã nhận diện đặc biệt
                    'message': 'Số dư không đủ',
                    'print_data': {
                        'title': 'YÊU CẦU NẠP TIỀN',
                        'ma_bn': f"BN{card.card_code}",
                        'ho_ten': patient.full_name,
                        'so_du': current_balance,
                        'tong_tien': total_pay,
                        'can_nap': missing_amount, # Số tiền cần nạp thêm
                        'qr_url': qr_url
                    }
                })

            # F. Trừ tiền & Cập nhật
            card.balance = current_balance - total_pay
        
            # Lấy tên dịch vụ để in phiếu
            service_list_data = []
        
            for inv in invoices:
                inv.status = 'Đã thanh toán'
                inv.payment_method = 'card' # Ghi nhận là thanh toán thẻ
                db.session.add(inv)
            
                for d in inv.details:
                    s = Service.query.get(d.service_id)
                    if s: service_list_data.append({
                        'name': s.service_name,
                        'price': float(d.unit_price) if d.unit_price else float(s.unit_price)
                        })

                # 2. [QUAN TRỌNG] CẬP NHẬT TRẠNG THÁI PHIÊN KHÁM -> CHỜ KHÁM
                sess = ExaminationSession.query.get(inv.examination_id)
                if sess:
                    # Chuyển sang 'processing' để bác sĩ thấy tên bệnh nhân trong danh sách
                    sess.status = 'Chờ khám' 
                    db.session.add(sess)

            db.session.commit()

            return jsonify({
                'success': True,
                'type': 'PAYMENT',
                'message': 'Thanh toán thành công',
                'print_data': {
                    'ma_bn': f"BN{card.card_code}",
                    'ho_ten': patient.full_name,
                    'services': service_list_data,
                    'total': total_pay,
                    'balance_left': card.balance
                }
            })

        # ============================================================
        # D. KHÔNG CÓ GÌ ĐỂ XỬ LÝ
        # ============================================================
        return jsonify({
            'success': False,
            'code': 'REDIRECT_RECEPTION',
            'message': f'Xin chào {patient.full_name}. Bạn không có lịch hẹn hoặc hóa đơn cần thanh toán.'
        }), 400

    except Exception as e:
        db.session.rollback()
        print("Lỗi Kiosk:", e)
        return jsonify({'success': False, 'message': 'Lỗi hệ thống: ' + str(e)}), 500