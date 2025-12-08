from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models import Staff, Account, Role, Position, Expertise, ClinicRoom
from werkzeug.security import generate_password_hash
from app.decorators import role_required

admin_staff_bp = Blueprint('admin_staff_bp', __name__)

@admin_staff_bp.route('/admin/quan-ly-nhan-vien', methods=['GET'])
@role_required(['Admin'])
def index():
    return render_template('quan_ly/quan_ly_nhan_vien.html')

# 1. API LẤY DANH SÁCH (CÓ PHÂN TRANG & TÌM KIẾM)
@admin_staff_bp.route('/api/admin/staffs', methods=['GET'])
def get_staffs():
    try:
        # Lấy tham số từ client
        page = request.args.get('page', 1, type=int)
        keyword = request.args.get('keyword', '').strip() # Lấy từ khóa tìm kiếm
        per_page = 7  # [YÊU CẦU] 8 dòng mỗi trang

        # Tạo Query cơ bản
        query = db.session.query(Staff, Account, Role, Position, Expertise)\
            .outerjoin(Account, Staff.account_id == Account.account_id)\
            .outerjoin(Role, Account.role_id == Role.role_id)\
            .outerjoin(Position, Staff.position_id == Position.position_id)\
            .outerjoin(Expertise, Staff.expertise_id == Expertise.expertise_id)

        # [LOGIC TÌM KIẾM] Nếu có keyword thì lọc theo tên hoặc username
        if keyword:
            search_str = f"%{keyword}%"
            query = query.filter(db.or_(
                Staff.full_name.ilike(search_str),
                Account.username.ilike(search_str)
            ))

        # Sắp xếp và Distinct để tránh trùng lặp
        query = query.distinct(Staff.staff_id).order_by(Staff.staff_id.desc())
        
        # Thực hiện phân trang
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        data = []
        for staff, acc, role, pos, exp in pagination.items:
            data.append({
                'id': staff.staff_id,
                'full_name': staff.full_name,
                'phone': staff.phone,
                'email': acc.email if acc else '',
                'username': acc.username if acc else '',
                'role_name': role.role_name if role else 'Chưa phân quyền',
                'position': pos.position_name if pos else '',
                'expertise': exp.expertise_name if exp else '',
                # ID phụ phục vụ việc sửa
                'role_id': acc.role_id if acc else '',
                'position_id': staff.position_id,
                'expertise_id': staff.expertise_id,
                'room_id': staff.room_id
            })
            
        return jsonify({
            'success': True, 
            'data': data,
            'pagination': {
                'current_page': page,
                'total_pages': pagination.pages,
                'total_records': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)}), 500

# 2. API METADATA (Dropdown)
@admin_staff_bp.route('/api/admin/staff-metadata', methods=['GET'])
def get_metadata():
    roles = Role.query.all()
    positions = Position.query.all()
    expertises = Expertise.query.all()
    rooms = ClinicRoom.query.all()
    
    return jsonify({
        'success': True,
        'roles': [{'id': r.role_id, 'name': r.role_name} for r in roles],
        'positions': [{'id': p.position_id, 'name': p.position_name} for p in positions],
        'expertises': [{'id': e.expertise_id, 'name': e.expertise_name} for e in expertises],
        'rooms': [{'id': r.room_id, 'name': r.room_name} for r in rooms]
    })

# 3. API LƯU (THÊM / SỬA)
@admin_staff_bp.route('/api/admin/staff/save', methods=['POST'])
@role_required(['Admin'])
def save_staff():
    try:
        data = request.json
        staff_id = data.get('id')
        
        full_name = data.get('full_name')
        phone = data.get('phone')
        email = data.get('email')
        username = data.get('username')
        password = data.get('password')
        role_id = data.get('role_id')
        position_id = data.get('position_id')
        expertise_id = data.get('expertise_id')
        room_id = data.get('room_id')

        if not full_name or not username:
            return jsonify({'success': False, 'message': 'Thiếu thông tin bắt buộc'}), 400

        # --- THÊM MỚI ---
        if not staff_id:
            if Account.query.filter_by(username=username).first():
                return jsonify({'success': False, 'message': 'Tên đăng nhập đã tồn tại!'}), 400
            
            # Tạo Account (Hash pass)
            new_acc = Account(
                username=username,
                email=email,
                role_id=role_id
            )
            new_acc.set_password(password if password else '123456') # Hàm set_password trong Model
            db.session.add(new_acc)
            db.session.flush()

            # Tạo Staff
            new_staff = Staff(
                full_name=full_name, phone=phone, account_id=new_acc.account_id,
                position_id=position_id, expertise_id=expertise_id, room_id=room_id
            )
            db.session.add(new_staff)
            msg = 'Thêm nhân viên thành công'

        # --- CẬP NHẬT ---
        else:
            staff = Staff.query.get(staff_id)
            if not staff: return jsonify({'success': False, 'message': 'Không tìm thấy'}), 404
            
            staff.full_name = full_name
            staff.phone = phone
            staff.position_id = position_id
            staff.expertise_id = expertise_id
            staff.room_id = room_id
            
            acc = Account.query.get(staff.account_id)
            if acc:
                acc.email = email
                acc.role_id = role_id
                if password and password.strip():
                    acc.set_password(password) # Đổi pass nếu nhập mới
            
            msg = 'Cập nhật thành công'

        db.session.commit()
        return jsonify({'success': True, 'message': msg})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# 4. API XÓA
@admin_staff_bp.route('/api/admin/staff/delete/<int:id>', methods=['DELETE'])
@role_required(['Admin'])
def delete_staff(id):
    try:
        staff = Staff.query.get(id)
        if not staff: return jsonify({'success': False}), 404
        
        acc_id = staff.account_id
        db.session.delete(staff)
        
        if acc_id:
            acc = Account.query.get(acc_id)
            if acc: db.session.delete(acc)
            
        db.session.commit()
        return jsonify({'success': True, 'message': 'Đã xóa thành công'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500