from flask_socketio import join_room
from app.extensions import db, socketio
from app.models import Notification

# 1. Xử lý khi Client (Flutter App) kết nối
@socketio.on('connect')
def handle_connect():
    print(">>> [Socket] Client Connected")

# 2. Xử lý khi Client gửi ID để định danh (Join Room)
@socketio.on('identify')
def handle_identify(data):
    """
    Flutter gửi: {'account_id': 10}
    Server sẽ đưa user này vào phòng riêng tên 'user_10'
    """
    account_id = data.get('account_id')
    if account_id:
        room = f"user_{account_id}"
        join_room(room)
        print(f">>> [Socket] User ID {account_id} joined room {room}")

# 3. Hàm tiện ích để các nơi khác gọi (Gửi thông báo)
def send_notification(account_id, type_notif, title, message):
    try:
        # A. Lưu vào Database
        notif = Notification(
            account_id=account_id,
            type=type_notif,
            title=title,
            message=message
        )
        db.session.add(notif)
        db.session.commit()

        # B. Bắn tin Socket Real-time
        payload = notif.to_dict()
        room = f"user_{account_id}"
        
        # 'receive_notification' là tên sự kiện App Flutter sẽ lắng nghe
        socketio.emit('receive_notification', payload, to=room)
        
        print(f">>> [Socket] Sent to {room}: {title}")
        
    except Exception as e:
        print(f"!!! Error sending notification: {e}")
        db.session.rollback()