var currentServicePage = 1;

$(document).ready(function() {
    loadCatalogs();
    loadServices(1);
    // [MỚI] Xử lý focus khi mở modal nhập liệu danh mục (modal chồng modal)
    $('#modalCatalogInput').on('shown.bs.modal', function () {
        $('#cat_name').focus();
    });
});

// ======================================
// [MỚI] HÀM MỞ MODAL QUẢN LÝ DANH MỤC LỚN
// ======================================
function openManageCatalogModal() {
    // Đảm bảo dữ liệu mới nhất được tải
    loadCatalogs();
    $('#modalManageCatalogs').modal('show');
}

// ======================================
// XỬ LÝ DANH MỤC (CATALOG) - ĐIỀU CHỈNH NHỎ
// ======================================
function loadCatalogs() {
    $.get('/api/admin/catalogs', function(res) {
        if(res.success) {
            var html = '';
            var options = '<option value="">-- Chọn danh mục --</option>';
            
            $.each(res.data, function(i, item) {
                // Render bảng trong modal
                html += `
                    <tr>
                        <td class="text-center">${item.id}</td>
                        <td>${item.name}</td>
                        <td class="text-center">
                            <button class="btn btn-sm btn-warning" onclick="editCatalog(${item.id}, '${item.name}')" title="Sửa">
                                <i class="fa-solid fa-pen"></i>
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="deleteCatalog(${item.id})" title="Xóa">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
                // Render dropdown
                options += `<option value="${item.id}">${item.name}</option>`;
            });
            $('#table_catalogs').html(html);
            $('#svc_catalog').html(options); 
            
            // Nếu không có dữ liệu thì hiện thông báo
            if (res.data.length === 0) {
                 $('#table_catalogs').html('<tr><td colspan="3" class="text-center text-muted fst-italic">Chưa có danh mục nào</td></tr>');
            }
        }
    });
}

// [SỬA TÊN MODAL ID] Mở modal nhập liệu nhỏ
function openCatalogModal() {
    $('#cat_id').val('');
    $('#cat_name').val('');
    $('#modalCatalogInput').modal('show'); // Sửa ID ở đây
}

// [SỬA TÊN MODAL ID] Mở modal sửa nhỏ
function editCatalog(id, name) {
    $('#cat_id').val(id);
    $('#cat_name').val(name);
    $('#modalCatalogInput').modal('show'); // Sửa ID ở đây
}

function saveCatalog() {
    var nameVal = $('#cat_name').val().trim();
    if(nameVal === "") {
        alert("Vui lòng nhập tên danh mục!");
        $('#cat_name').focus();
        return;
    }

    var data = {
        id: $('#cat_id').val(),
        name: nameVal
    };
    
    // Disable nút lưu để tránh bấm nhiều lần
    var btnSave = $('#modalCatalogInput .btn-success');
    var originalText = btnSave.html();
    btnSave.html('<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...').prop('disabled', true);

    $.ajax({
        url: '/api/admin/catalogs/save',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(res) {
            if(res.success) {
                // alert(res.message); // Không cần alert nữa cho mượt
                $('#modalCatalogInput').modal('hide'); // Đóng modal nhập liệu
                loadCatalogs(); // Tải lại bảng danh mục trong modal lớn
            } else {
                alert(res.message);
            }
        },
        complete: function() {
             // Enable lại nút lưu
             btnSave.html(originalText).prop('disabled', false);
        }
    });
}

function deleteCatalog(id) {
    if(!confirm("Bạn có chắc muốn xóa danh mục này?")) return;
    $.ajax({
        url: '/api/admin/catalogs/delete/' + id,
        type: 'DELETE',
        success: function(res) {
            if(res.success) {
                loadCatalogs();
            } else {
                alert(res.message);
            }
        }
    });
}

// ======================================
// XỬ LÝ DỊCH VỤ (SERVICE)
// ======================================
// Nhận tham số page (mặc định = 1)
function loadServices(page = 1) {
    currentServicePage = page; // Lưu lại trang hiện tại

    $.get('/api/admin/services', { page: page }, function(res) {
        if(res.success) {
            var html = '';
            
            // 1. Render Dữ liệu bảng
            if (res.data.length === 0) {
                html = '<tr><td colspan="5" class="text-center">Không có dữ liệu</td></tr>';
            } else {
                // Tính STT: (Trang hiện tại - 1) * 10 + index + 1
                var startIndex = (res.pagination.current_page - 1) * 10;
                
                $.each(res.data, function(i, item) {
                    var priceFormatted = new Intl.NumberFormat('vi-VN').format(item.price);
                    html += `
                        <tr>
                            <td class="text-center">${startIndex + i + 1}</td>
                            <td >${item.name}</td>
                            <td><span >${item.catalog_name}</span></td>
                            <td class="text-end">${priceFormatted}</td>
                            <td class="text-center">
                                <button class="btn btn-sm btn-warning" onclick="editService(${item.id}, '${item.name}', ${item.price}, ${item.catalog_id})">
                                    <i class="fa-solid fa-pen"></i>
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="deleteService(${item.id})">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                });
            }
            $('#table_services').html(html);

            // 2. Render Thanh phân trang
            renderPagination(res.pagination);
        }
    });
}

// Hàm vẽ nút phân trang
function renderPagination(pg) {
    var html = '';
    
    // Nút Trước (Previous)
    if (pg.has_prev) {
        html += `<li class="page-item">
                    <a class="page-link" href="javascript:void(0)" onclick="loadServices(${pg.current_page - 1})">Trước</a>
                 </li>`;
    } else {
        html += `<li class="page-item disabled"><span class="page-link">Trước</span></li>`;
    }

    // Các nút số trang (1, 2, 3...)
    for (var i = 1; i <= pg.total_pages; i++) {
        var activeClass = (i === pg.current_page) ? 'active' : '';
        html += `<li class="page-item ${activeClass}">
                    <a class="page-link" href="javascript:void(0)" onclick="loadServices(${i})">${i}</a>
                 </li>`;
    }

    // Nút Sau (Next)
    if (pg.has_next) {
        html += `<li class="page-item">
                    <a class="page-link" href="javascript:void(0)" onclick="loadServices(${pg.current_page + 1})">Sau</a>
                 </li>`;
    } else {
        html += `<li class="page-item disabled"><span class="page-link">Sau</span></li>`;
    }

    $('#service_pagination').html(html);
}

function openServiceModal() {
    $('#svc_id').val('');
    $('#svc_name').val('');
    $('#svc_price').val('');
    $('#svc_catalog').val('');
    $('#modalService').modal('show');
}

function editService(id, name, price, cat_id) {
    $('#svc_id').val(id);
    $('#svc_name').val(name);
    $('#svc_price').val(price);
    $('#svc_catalog').val(cat_id);
    $('#modalService').modal('show');
}

function saveService() {
    var data = {
        id: $('#svc_id').val(),
        name: $('#svc_name').val(),
        price: $('#svc_price').val(),
        catalog_id: $('#svc_catalog').val()
    };
    
    $.ajax({
        url: '/api/admin/services/save',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(res) {
            if(res.success) {
                alert(res.message);
                $('#modalService').modal('hide');
                loadServices(currentServicePage);
            } else {
                alert(res.message);
            }
        }
    });
}

function deleteService(id) {
    if(!confirm("Xóa dịch vụ này?")) return;
    $.ajax({
        url: '/api/admin/services/delete/' + id,
        type: 'DELETE',
        success: function(res) {
            if(res.success) {
                loadServices(currentServicePage);
            } else {
                alert(res.message);
            }
        }
    });
}