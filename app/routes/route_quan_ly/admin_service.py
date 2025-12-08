from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models import Service, CatalogServices
from app.decorators import role_required

admin_service_bp = Blueprint('admin_service_bp', __name__)

# --- VIEW: Trả về giao diện quản lý ---
@admin_service_bp.route('/admin/quan-ly-dich-vu', methods=['GET'])
@role_required(['Admin'])
def index():
    return render_template('quan_ly/quan_ly_dich_vu.html')

# =======================================================
# 1. QUẢN LÝ DANH MỤC (CATALOG)
# =======================================================

# Lấy danh sách danh mục
@admin_service_bp.route('/api/admin/catalogs', methods=['GET'])
def get_catalogs():
    try:
        catalogs = CatalogServices.query.all()
        result = [{
            'id': c.catalogservice_id, 
            'name': c.catalogservice_name
        } for c in catalogs]
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Thêm mới / Cập nhật danh mục
@admin_service_bp.route('/api/admin/catalogs/save', methods=['POST'])
def save_catalog():
    try:
        data = request.json
        cat_id = data.get('id') # Nếu có ID là sửa, không có là thêm
        name = data.get('name')

        if not name:
            return jsonify({'success': False, 'message': 'Tên danh mục không được để trống'}), 400

        if cat_id:
            # Update
            cat = CatalogServices.query.get(cat_id)
            if not cat:
                return jsonify({'success': False, 'message': 'Không tìm thấy danh mục'}), 404
            cat.catalogservice_name = name
            msg = 'Cập nhật thành công'
        else:
            # Create
            new_cat = CatalogServices(catalogservice_name=name)
            db.session.add(new_cat)
            msg = 'Thêm mới thành công'

        db.session.commit()
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Xóa danh mục
@admin_service_bp.route('/api/admin/catalogs/delete/<int:id>', methods=['DELETE'])
def delete_catalog(id):
    try:
        cat = CatalogServices.query.get(id)
        if not cat:
            return jsonify({'success': False, 'message': 'Không tìm thấy'}), 404
        
        # Kiểm tra xem danh mục có dịch vụ con không?
        if cat.service: # relationship backref='service'
            return jsonify({'success': False, 'message': 'Danh mục này đang chứa dịch vụ, không thể xóa!'}), 400

        db.session.delete(cat)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Đã xóa danh mục'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# =======================================================
# 2. QUẢN LÝ DỊCH VỤ (SERVICE)
# =======================================================

# Lấy danh sách dịch vụ (Kèm tên danh mục)
@admin_service_bp.route('/api/admin/services', methods=['GET'])
def get_services():
    try:
        # 1. Lấy số trang từ client gửi lên (mặc định là 1)
        page = request.args.get('page', 1, type=int)
        per_page = 8 # Cố định 10 record / trang
        
        # 2. Tạo Query (Chưa execute vội)
        query = db.session.query(Service, CatalogServices)\
            .join(CatalogServices, Service.catalogservice_id == CatalogServices.catalogservice_id)\
            .order_by(Service.service_id.desc()) # Sắp xếp mới nhất lên đầu

        # 3. Thực hiện phân trang
        # error_out=False: để nếu trang không tồn tại thì trả về list rỗng thay vì lỗi 404
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # 4. Lấy dữ liệu của trang hiện tại
        result = []
        for svc, cat in pagination.items:
            result.append({
                'id': svc.service_id,
                'name': svc.service_name,
                'price': float(svc.unit_price),
                'catalog_id': svc.catalogservice_id,
                'catalog_name': cat.catalogservice_name
            })
            
        # 5. Trả về cả dữ liệu và thông tin phân trang
        return jsonify({
            'success': True, 
            'data': result,
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

# Thêm mới / Cập nhật dịch vụ
@admin_service_bp.route('/api/admin/services/save', methods=['POST'])
@role_required(['Admin'])
def save_service():
    try:
        data = request.json
        svc_id = data.get('id')
        name = data.get('name')
        price = data.get('price')
        catalog_id = data.get('catalog_id')

        if not name or not price or not catalog_id:
            return jsonify({'success': False, 'message': 'Vui lòng nhập đủ thông tin'}), 400

        if svc_id:
            # Update
            svc = Service.query.get(svc_id)
            if not svc: return jsonify({'success': False, 'message': 'Không tìm thấy'}), 404
            svc.service_name = name
            svc.unit_price = price
            svc.catalogservice_id = catalog_id
            msg = 'Cập nhật dịch vụ thành công'
        else:
            # Create
            new_svc = Service(
                service_name=name,
                unit_price=price,
                catalogservice_id=catalog_id
            )
            db.session.add(new_svc)
            msg = 'Thêm dịch vụ thành công'

        db.session.commit()
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# Xóa dịch vụ
@admin_service_bp.route('/api/admin/services/delete/<int:id>', methods=['DELETE'])
@role_required(['Admin'])
def delete_service(id):
    try:
        svc = Service.query.get(id)
        if not svc:
            return jsonify({'success': False, 'message': 'Không tìm thấy'}), 404
        
        # Kiểm tra xem dịch vụ đã được sử dụng trong hóa đơn/chỉ định chưa?
        # (Bạn nên check bảng ServiceOrder hoặc InvoiceDetail ở đây để tránh lỗi toàn vẹn dữ liệu)
        # Ví dụ: if svc.orders: return lỗi...
        
        db.session.delete(svc)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Đã xóa dịch vụ'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500