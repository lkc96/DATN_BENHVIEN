from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models import Notification, SessionRooms, ExaminationSession, Patient, ServiceOrder
from app.socket_events import send_notification # Import hàm gửi thông báo

doctor_bp = Blueprint('doctor_notification_bp', __name__)

# 1. API GỌI SỐ KHÁM (QUEUE)
@doctor_bp.route('/api/doctor/call-number', methods=['POST'])
def call_number():
    # Payload gửi lên: { "room_id": 1, "number_order": 5 }
    data = request.json
    room_id = data.get('room_id')
    current_number = data.get('number_order')

    # Logic: Tìm những người có số > số hiện tại để báo chuẩn bị
    # Lấy 3 người tiếp theo
    waiting_list = SessionRooms.query.filter(
        SessionRooms.room_id == room_id,
        SessionRooms.number_order >= current_number,
        SessionRooms.number_order <= current_number + 2
    ).all()

    for item in waiting_list:
        # Truy ngược tìm Patient -> Account
        exam = ExaminationSession.query.get(item.examination_id)
        if exam:
            patient = Patient.query.get(exam.patient_id)
            if patient and patient.account_id:
                diff = item.number_order - current_number
                
                title = "Thông báo số chờ"
                msg = ""
                
                if diff == 0:
                    title = "MỜI VÀO KHÁM NGAY"
                    msg = f"Đã đến lượt số {item.number_order}. Mời bạn vào phòng khám ngay."
                elif diff == 1:
                    msg = f"Chuẩn bị! Bạn còn 1 lượt nữa (Số của bạn: {item.number_order})."
                elif diff == 2:
                    msg = f"Sắp đến lượt bạn (Số của bạn: {item.number_order}). Vui lòng chú ý."

                # Gọi hàm bắn thông báo
                send_notification(patient.account_id, 'queue', title, msg)

    return jsonify({"message": "Đã gọi số"}), 200

@doctor_bp.route('/api/notifications/<int:account_id>', methods=['GET'])
def get_notifications_history(account_id):
    try:
        # Lấy tất cả thông báo của account_id
        # Sắp xếp: Mới nhất lên đầu (desc)
        notifs = Notification.query.filter_by(account_id=account_id)\
            .order_by(Notification.create_date.desc())\
            .all()
        
        # Chuyển đổi sang dạng List Dictionary để trả về JSON
        result = []
        for n in notifs:
            result.append({
                "id": n.notification_id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                # Format ngày giờ thành chuỗi
                "time": n.create_date.strftime("%H:%M %d/%m/%Y") if n.create_date else "",
                "isRead": n.is_read
            })

        return jsonify(result), 200
    except Exception as e:
        print(f"Lỗi lấy lịch sử thông báo: {e}")
        return jsonify({"error": str(e)}), 500

@doctor_bp.route('/api/notification/read/<int:notification_id>', methods=['PUT'])
def mark_notification_read(notification_id):
    try:
        # 1. Tìm thông báo theo ID
        notif = Notification.query.get(notification_id)
        
        if not notif:
            return jsonify({"success": False, "message": "Không tìm thấy thông báo"}), 404

        # 2. Cập nhật trạng thái
        notif.is_read = True
        notif.create_date = notif.create_date # Giữ nguyên ngày tạo, chỉ update trạng thái
        
        db.session.commit()
        
        return jsonify({"success": True, "message": "Đã đánh dấu đã đọc"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500