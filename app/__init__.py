from flask import Flask, render_template
from flask_cors import CORS
from app.config import Config
from app.extensions import db, migrate, socketio
from flask_login import LoginManager

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Khởi tạo extensions
    db.init_app(app)
    socketio.init_app(app)
    migrate.init_app(app, db)
    CORS(app) # Cho phép gọi API từ bên ngoài (Frontend)

    # Cấu hình Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth_bp.login' # Tên route trang login
    login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."

    from app.models import Account

    @login_manager.user_loader
    def load_user(user_id):
        return Account.query.get(int(user_id))
    
    # Đăng ký Routes
    
    from .routes.route_web.tiep_don import tiep_don_bp
    from .routes.route_quan_ly.main import main_bp
    from .routes.route_web.auth import auth_bp
    from .routes.route_web.kham_benh import kham_benh_bp
    from .routes.route_web.kiosk import kiosk_bp
    from .routes.route_quan_ly.admin_service import admin_service_bp
    from .routes.route_quan_ly.admin_staff import admin_staff_bp
    from .routes.route_quan_ly.admin_patient import admin_patient_bp


    from .routes.route_mobile.auth_mobile import auth_mobile_bp
    from .routes.route_mobile.home_mobile import home_bp
    from .routes.route_mobile.profile import profile_bp
    from .routes.route_mobile.appointment import appointment_bp
    from .routes.route_mobile.health_profile import health_bp
    from .routes.route_quan_ly.notification_trigger import doctor_bp
    


    
    app.register_blueprint(tiep_don_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(kham_benh_bp)
    app.register_blueprint(kiosk_bp)
    app.register_blueprint(admin_service_bp)
    app.register_blueprint(admin_staff_bp)
    app.register_blueprint(admin_patient_bp)

    app.register_blueprint(auth_mobile_bp, url_prefix='/auth')
    app.register_blueprint(home_bp, url_prefix='/home')
    app.register_blueprint(profile_bp)
    app.register_blueprint(appointment_bp, url_prefix='/api')
    app.register_blueprint(health_bp, url_prefix='/health')
    app.register_blueprint(doctor_bp)


    with app.app_context():
        # Import file socket_events.py vừa tạo
        from app import socket_events
        
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('403.html'), 403
    return app