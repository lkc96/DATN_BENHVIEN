from flask import Blueprint, render_template, request, jsonify
from app.extensions import db
from app.models import MagneticCard, Patient, Invoice, ExaminationSession, Service

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