from app.extensions import db
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

def get_vn_time():
    return datetime.utcnow() + timedelta(hours=7)

class Role(db.Model):
    __tablename__ = 'roles'
    
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    
    # Quan hệ: 1 Role có nhiều Account
    accounts = db.relationship('Account', backref='role', lazy=True)

    

class Account(db.Model, UserMixin):
    __tablename__ = 'accounts'
    
    account_id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    create_date = db.Column(db.DateTime, default=get_vn_time)
    
    # Quan hệ 1-1: Account <-> Staff hoặc Patient
    staff = db.relationship('Staff', backref='account', uselist=False)
    patient = db.relationship('Patient', backref='account', uselist=False)

    # Override phương thức get_id của UserMixin (Flask-Login cần cái này)
    def get_id(self):
        return str(self.account_id)

    # Hàm kiểm tra mật khẩu
    def check_password(self, password_input):
        return check_password_hash(self.password, password_input)
    
    # Hàm set mật khẩu (tiện dụng khi tạo user)
    def set_password(self, password_input):
        self.password = generate_password_hash(password_input)


class Position(db.Model):
    __tablename__ = 'positions'
    
    position_id = db.Column(db.Integer, primary_key=True)
    position_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

class Expertise(db.Model):
    __tablename__ = 'expertises'
    
    expertise_id = db.Column(db.Integer, primary_key=True)
    expertise_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

class ClinicRoom(db.Model):
    __tablename__ = 'clinicrooms' # Lưu ý: Postgres thường viết thường hết
    
    room_id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(100), nullable=False)
    function = db.Column(db.Text)
    room_number = db.Column(db.String(50))

# Thêm vào app/models.py

class SessionRooms(db.Model):
    __tablename__ = 'sessionrooms'
    
    session_room_id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinationsessions.examination_id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('clinicrooms.room_id'), nullable=False)
    
    number_order = db.Column(db.Integer, nullable=False) 
    patient_name = db.Column(db.String(100))
    age = db.Column(db.Integer)

class Staff(db.Model):
    __tablename__ = 'staffs'
    
    staff_id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.account_id'), unique=True)
    room_id = db.Column(db.Integer, db.ForeignKey('clinicrooms.room_id'))
    position_id = db.Column(db.Integer, db.ForeignKey('positions.position_id'))
    expertise_id = db.Column(db.Integer, db.ForeignKey('expertises.expertise_id'))
    full_name = db.Column(db.String(100), nullable=False)
    date_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    description = db.Column(db.Text)

    position = db.relationship('Position', backref='staffs')   # Để gọi staff.position.position_name
    expertise = db.relationship('Expertise', backref='staffs') # Để gọi staff.expertise.expertise_name
    room = db.relationship('ClinicRoom', backref='staffs')



class Patient(db.Model):
    __tablename__ = 'patients'
    
    patient_id = db.Column(db.Integer, primary_key=True)
    # Lưu ý: Trong SQL bạn có cả card_id ở đây và patient_id ở bảng Card
    # Để tránh lỗi vòng lặp, ta khai báo ForeignKey nhưng để nullable=True
    card_id = db.Column(db.Integer, db.ForeignKey('magneticcards.card_id'), nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.account_id'), unique=True, nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    date_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    address = db.Column(db.Text)
    id_number = db.Column(db.String(20), unique=True)
    phone = db.Column(db.String(20))
    description = db.Column(db.Text)

    # Quan hệ ngược để truy xuất lịch sử khám
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    exams = db.relationship('ExaminationSession', backref='patient', lazy=True)

class MagneticCard(db.Model):
    __tablename__ = 'magneticcards'
    
    card_id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'))
    card_code = db.Column(db.String(100), unique=True, nullable=False)
    create_date = db.Column(db.DateTime, default=get_vn_time)
    status = db.Column(db.String(50))
    balance = db.Column(db.Numeric(15, 2), default=0)

    # Relationship 1-1 với Patient
    # remote_side giúp SQLAlchemy hiểu quan hệ vòng tròn này (nếu cần thiết)
    # Ở đây ta dùng backref đơn giản để từ Thẻ lấy được thông tin Bệnh nhân
    patient_ref = db.relationship("Patient", foreign_keys=[patient_id], backref="linked_card")


class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    appointment_id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('clinicrooms.room_id'))
    appointment_time = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(50))

    room = db.relationship('ClinicRoom', backref='appointments')

class ExaminationSession(db.Model):
    __tablename__ = 'examinationsessions'
    
    examination_id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.appointment_id'))
    room_id = db.Column(db.Integer, db.ForeignKey('clinicrooms.room_id'))
    create_date = db.Column(db.DateTime, default=get_vn_time)
    symptom = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    doctor_advice = db.Column(db.Text)
    reason = db.Column(db.Text)
    status = db.Column(db.String(50))
    
    # Quan hệ xuống các bảng chi tiết
    prescriptions = db.relationship('Prescription', backref='session', lazy=True)
    service_orders = db.relationship('ServiceOrder', backref='session', lazy=True)
    invoices = db.relationship('Invoice', backref='session', lazy=True)

class CatalogServices(db.Model):
    __tablename__ = 'catalogservices'

    catalogservice_id = db.Column(db.Integer, primary_key = True)
    catalogservice_name = db.Column(db.String(200), nullable=False)

    service = db.relationship('Service', backref='catalogservice', lazy=True)


class Service(db.Model):
    __tablename__ = 'services'
    
    service_id = db.Column(db.Integer, primary_key=True)
    catalogservice_id = db.Column(db.Integer, db.ForeignKey('catalogservices.catalogservice_id'), nullable=False)
    service_name = db.Column(db.String(200), nullable=False)
    unit_price = db.Column(db.Numeric(15, 2), nullable=False)

class ServiceOrder(db.Model):
    __tablename__ = 'serviceorders'
    
    service_order_id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinationsessions.examination_id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.service_id'), nullable=False)
    status = db.Column(db.String(50))
    result = db.Column(db.Text)
    description = db.Column(db.Text)
    ticket_code = db.Column(db.String(50))
    
    # Để lấy tên dịch vụ từ order: order.service_info.service_name
    service_info = db.relationship('Service', backref='orders')


class Medicine(db.Model):
    __tablename__ = 'medicines'
    
    medicine_id = db.Column(db.Integer, primary_key=True)
    medicine_name = db.Column(db.String(200), nullable=False)
    generic_name = db.Column(db.String(200))
    strength = db.Column(db.String(100))
    active_element = db.Column(db.String(200))
    unit = db.Column(db.String(50))

class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    
    prescription_id = db.Column(db.Integer, primary_key=True)
    # Trong SQL bạn đặt tên cột này là examination_session_id
    examination_session_id = db.Column(db.Integer, db.ForeignKey('examinationsessions.examination_id'))
    create_date = db.Column(db.DateTime, default=get_vn_time)
    
    details = db.relationship('PrescriptionDetail', backref='prescription', lazy=True)

class PrescriptionDetail(db.Model):
    __tablename__ = 'prescriptiondetails'
    
    prescription_detail_id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.prescription_id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.medicine_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    dosage = db.Column(db.Text)

    medicine = db.relationship('Medicine')



class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    invoice_id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinationsessions.examination_id'))
    create_date = db.Column(db.DateTime, default=get_vn_time)
    total_amount = db.Column(db.Numeric(15, 2))
    status = db.Column(db.String(50))
    payment_method = db.Column(db.String(50))
    
    details = db.relationship('InvoiceDetail', backref='invoice', lazy=True)

class InvoiceDetail(db.Model):
    __tablename__ = 'invoicedetails'
    
    invoice_detail_id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.invoice_id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.service_id'))
    unit_price = db.Column(db.Numeric(15, 2))

class ICD10(db.Model):
    __tablename__ = 'icd10'
    
    code = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(500), nullable=False)
    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name
        }

class DiagnosisRecord(db.Model):
    # Tên bảng phải khớp y hệt trong SQL (lưu ý chữ thường/số nhiều)
    __tablename__ = 'diagnosisrecords' 
    
    record_id = db.Column(db.Integer, primary_key=True)
    
    # Khóa ngoại liên kết 1-1 với phiên khám
    examination_id = db.Column(db.Integer, db.ForeignKey('examinationsessions.examination_id'), unique=True, nullable=False)
    
    # --- Chỉ số sinh tồn ---
    height = db.Column(db.Numeric(5, 2))       # Chiều cao
    weight = db.Column(db.Numeric(5, 2))       # Cân nặng
    temperature = db.Column(db.Numeric(4, 1))  # Nhiệt độ
    blood_pressure = db.Column(db.String(20))  # Huyết áp
    pulse = db.Column(db.Integer)              # Mạch
    bmi = db.Column(db.Numeric(5, 2))          # BMI
    
    # --- Chẩn đoán ---
    clinical_symptoms = db.Column(db.Text)     # Triệu chứng lâm sàng
    
    # Mã bệnh chính (Liên kết bảng ICD10)
    main_disease_code = db.Column(db.String(20), db.ForeignKey('icd10.code'))
    
    # Bệnh phụ (Lưu text mô tả hoặc mã)
    sub_disease_code = db.Column(db.String(200)) 
    
    doctor_advice = db.Column(db.Text)         # Lời dặn
    treatment_plan = db.Column(db.Text)        # Hướng xử trí
    
    re_examination_date = db.Column(db.Date)   # Ngày hẹn tái khám

    # --- Relationships (Để tiện truy vấn) ---
    main_icd = db.relationship('ICD10', foreign_keys=[main_disease_code])


class Notification(db.Model):
    __tablename__ = 'notifications'

    notification_id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.account_id'), nullable=False)
    
    # Các loại: 'appointment', 'result', 'payment', 'reminder', 'complete', 'queue'
    type = db.Column(db.String(50)) 
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    create_date = db.Column(db.DateTime, default=get_vn_time) # Sử dụng hàm get_vn_time có sẵn của bạn

    def to_dict(self):
        """Helper để chuyển object sang dict trả về JSON"""
        return {
            "id": self.notification_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "time": self.create_date.strftime("%H:%M %d/%m/%Y"), # Format ngày giờ VN
            "isRead": self.is_read
        }