from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func, extract, case
from datetime import datetime, date, timedelta

# Import db và Models
from app.extensions import db
from app.models import (
    ClinicRoom, ExaminationSession, MagneticCard, Patient, Invoice, Staff, 
    DiagnosisRecord
)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    # --- THIẾT LẬP THỜI GIAN ---
    today = date.today()
    start_of_month = today.replace(day=1) # Ngày mùng 1 đầu tháng
    seven_days_ago = today - timedelta(days=6) # 7 ngày trước (tính cả hôm nay)

    # =====================================================
    # PHẦN 1: CÁC CHỈ SỐ STATS (TOP CARDS)
    # =====================================================
    
    # 1.1 Tổng bệnh nhân tiếp đón
    patients_today_count = ExaminationSession.query.filter(
        func.date(ExaminationSession.create_date) == today
    ).count()
    
    # 1.2 Số bệnh nhân đang chờ (Lọc theo tiếng Việt)
    waiting_count = ExaminationSession.query.filter(
        ExaminationSession.status == 'Chờ khám', 
        func.date(ExaminationSession.create_date) == today
    ).count()
    
    # 1.3 Bác sĩ đang trực
    doctors_active_count = Staff.query.filter(Staff.room_id != None).count()
    
    # 1.4 DOANH THU HÔM NAY (Xử lý tài chính)
    # - Logic: Tính tổng 'total_amount' của Invoice có status 'Đã thanh toán' trong hôm nay
    # - func.coalesce(..., 0): Để trả về số 0 nếu chưa có hóa đơn nào (tránh lỗi None)
    revenue_today = db.session.query(
        func.coalesce(func.sum(Invoice.total_amount), 0)
    ).filter(
        func.date(Invoice.create_date) == today, 
        Invoice.status == 'Đã thanh toán' 
    ).scalar()
    
    # Format số tiền thành dạng "15.2M" hoặc "500K" cho gọn
    if revenue_today >= 1000000:
        revenue_formatted = "{:,.1f}M".format(revenue_today / 1000000)
    else:
        revenue_formatted = "{:,.0f}".format(revenue_today)

    stats_data = {
        "patients_today": patients_today_count,
        "waiting": waiting_count,
        "revenue": revenue_formatted,
        "doctors_active": doctors_active_count
    }

    # =====================================================
    # PHẦN 2: DỮ LIỆU BIỂU ĐỒ (CHARTS)
    # =====================================================

    # --- CHART 1: LƯU LƯỢNG KHÁM (Theo giờ) ---
    traffic_query = db.session.query(
        func.extract('hour', ExaminationSession.create_date).label('h'),
        func.count(ExaminationSession.examination_id)
    ).filter(
        func.date(ExaminationSession.create_date) == today
    ).group_by('h').all()

    traffic_dict = {h: 0 for h in range(7, 18)} # Khung giờ hành chính 7h-17h
    for h, count in traffic_query:
        if 7 <= h <= 17: traffic_dict[int(h)] = count

    # --- CHART 2: PHÂN BỐ CHUYÊN KHOA ---
    room_query = db.session.query(ClinicRoom.room_name).join(
        ExaminationSession, ExaminationSession.room_id == ClinicRoom.room_id
    ).filter(
        func.date(ExaminationSession.create_date) == today
    ).all()

    specialty_counts = {"Nội": 0, "Ngoại": 0, "Tai Mũi Họng": 0, "Nhi": 0, "Mắt": 0, "Khác": 0}
    for row in room_query:
        name = row[0].lower()
        if "nội" in name: specialty_counts["Nội"] += 1
        elif "ngoại" in name: specialty_counts["Ngoại"] += 1
        elif "nhi" in name: specialty_counts["Nhi"] += 1
        elif "mắt" in name: specialty_counts["Mắt"] += 1
        elif "tai" in name or "họng" in name: specialty_counts["Tai Mũi Họng"] += 1
        else: specialty_counts["Khác"] += 1

    # --- CHART 3 (MỚI): XU HƯỚNG DOANH THU 7 NGÀY ---
    # Logic: Group by ngày, Sum tổng tiền, Filter 'Đã thanh toán'
    rev_trend_query = db.session.query(
        func.date(Invoice.create_date).label('day'), 
        func.sum(Invoice.total_amount)
    ).filter(
        Invoice.create_date >= seven_days_ago, 
        Invoice.status == 'Đã thanh toán'
    ).group_by('day').all()
    
    # Tạo dict chứa 7 ngày gần nhất, mặc định giá trị = 0
    trend_dict = { (seven_days_ago + timedelta(days=i)): 0 for i in range(7) }
    
    # Điền dữ liệu thật vào dict
    for r_day, r_amount in rev_trend_query:
        # Lưu ý: r_day có thể là object date, cần đảm bảo khớp key
        if r_day in trend_dict:
            trend_dict[r_day] = int(r_amount)

    # --- CHART 4 (MỚI): HÌNH THỨC THANH TOÁN (Tháng này) ---
    pay_method_query = db.session.query(
        Invoice.payment_method, 
        func.count(Invoice.invoice_id)
    ).filter(
        Invoice.create_date >= start_of_month, 
        Invoice.status == 'Đã thanh toán'
    ).group_by(Invoice.payment_method).all()

    # ĐÓNG GÓI DỮ LIỆU CHART ĐỂ GỬI SANG HTML
    final_chart_data = {
        "traffic": {
            "labels": [f"{h}h" for h in traffic_dict.keys()],
            "values": list(traffic_dict.values())
        },
        "disease": {
            "labels": list(specialty_counts.keys()),
            "values": list(specialty_counts.values())
        },
        "revenue_trend": {
            "labels": [d.strftime("%d/%m") for d in trend_dict.keys()], # Format ngày dd/mm
            "values": list(trend_dict.values())
        },
        "payment": {
            "labels": [p[0] if p[0] else "Khác" for p in pay_method_query],
            "values": [p[1] for p in pay_method_query]
        }
    }

    # =====================================================
    # PHẦN 3: DANH SÁCH CHỜ (PATIENT QUEUE)
    # =====================================================
    
    # Sắp xếp ưu tiên: Cấp cứu -> Tiếp nhận -> Chờ khám -> Đang khám -> Hoàn thành
    sorter = case(
        (ExaminationSession.status == 'Cấp cứu', 0),
        (ExaminationSession.status == 'Tiếp nhận', 1),
        (ExaminationSession.status == 'Chờ khám', 2),
        (ExaminationSession.status == 'Đang khám', 3),
        (ExaminationSession.status == 'Hoàn thành', 4),
        else_=5
    )

    queue_query = db.session.query(
        ExaminationSession, 
        Patient, 
        MagneticCard.card_code  # <--- Lấy thêm cột card_code
    ).join(
        Patient, ExaminationSession.patient_id == Patient.patient_id
    ).outerjoin( # Dùng Outer Join để không bị mất bệnh nhân nếu chưa có thẻ
        MagneticCard, Patient.card_id == MagneticCard.card_id
    ).filter(
        func.date(ExaminationSession.create_date) == today
    ).order_by(
        sorter.asc(),
        ExaminationSession.create_date.asc()
    ).all()

    patient_queue_list = []
    
    # --- VÒNG LẶP MỚI (Unpack 3 biến) ---
    for sess, pat, card_code in queue_query:
        time_str = sess.create_date.strftime("%H:%M") if sess.create_date else ""
        
        # LOGIC TẠO MÃ BỆNH NHÂN:
        # Nếu có card_code -> BN + card_code
        # Nếu không có -> BN + id_number (CCCD) hoặc BN + patient_id
        if card_code:
            display_id = f"BN{card_code}"
        elif pat.id_number:
            display_id = f"{pat.id_number}"
        else:
            display_id = f"BN{pat.patient_id}"
        
        patient_queue_list.append({
            "id": display_id,
            "name": pat.full_name,
            "age": (today.year - pat.date_birth.year) if pat.date_birth else "N/A",
            "time": time_str,
            "status": sess.status # Giữ nguyên status Tiếng Việt để HTML xử lý màu
        })

    return render_template('dashboard.html',
                           user=current_user,
                           stats=stats_data, 
                           patients=patient_queue_list,
                           chart_data=final_chart_data,
                           page_title="Tổng quan Bệnh viện")