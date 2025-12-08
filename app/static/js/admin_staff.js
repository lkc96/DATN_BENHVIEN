var currentStaffPage = 1; 
var currentKeyword = ""; // Lưu từ khóa tìm kiếm

$(document).ready(function() {
    loadMetadata(); 
    loadStaffs(1); 

    // Bắt sự kiện nhấn Enter ở ô tìm kiếm
    $('#staff_search').on('keypress', function(e) {
        if(e.which == 13) {
            searchStaff();
        }
    });
});

// 1. Load Dropdown
function loadMetadata() {
    $.get('/api/admin/staff-metadata', function(res) {
        if(res.success) {
            fillSelect('#st_role', res.roles);
            fillSelect('#st_position', res.positions);
            fillSelect('#st_expertise', res.expertises);
            fillSelect('#st_room', res.rooms);
        }
    });
}

function fillSelect(selector, data) {
    var html = '<option value="">-- Chọn --</option>';
    if (data) {
        data.forEach(item => {
            html += `<option value="${item.id}">${item.name}</option>`;
        });
    }
    $(selector).html(html);
}

// 2. Tìm kiếm nhân viên
function searchStaff() {
    currentKeyword = $('#staff_search').val(); // Lấy giá trị ô input
    loadStaffs(1); // Tìm kiếm thì luôn reset về trang 1
}

// 3. Load Danh sách & Phân trang
function loadStaffs(page = 1) {
    currentStaffPage = page;

    $.ajax({
        url: '/api/admin/staffs',
        type: 'GET',
        data: { 
            page: page, 
            keyword: currentKeyword // Gửi kèm từ khóa
        },
        success: function(res) {
            if(res.success) {
                var html = '';
                
                if(!res.data || res.data.length === 0) {
                    $('#table_staffs').html('<tr><td colspan="6" class="text-center py-5 text-muted fst-italic">Không tìm thấy dữ liệu</td></tr>');
                } else {
                    var startIndex = (res.pagination.current_page - 1) * 8; // Per page = 8

                    $.each(res.data, function(i, item) {
                        
                        // Màu sắc Badge Vai trò
                        var badgeClass = 'bg-secondary';
                        if(item.role_name === 'Bác sĩ') badgeClass = 'bg-success';
                        else if(item.role_name === 'Lễ tân') badgeClass = 'bg-info text-dark';
                        else if(item.role_name === 'Admin') badgeClass = 'bg-danger';

                        html += `
                            <tr>
                                <td class="text-center">${startIndex + i + 1}</td>
                                
                                <td>
                                    <a>
                                        ${item.full_name}
                                    </a>
                                </td>
                                
                                <td>
                                    <div class="d-flex flex-column">
                                        <span class="fw-bold text-dark small">${item.username}</span>
                                        <span class="small text-muted" style="font-size: 0.75rem;">${item.email}</span>
                                    </div>
                                </td>
                                
                                <td>
                                    <div class="d-flex align-items-center">
                                        <div class="d-flex flex-column">
                                            <span class="small fw-bold">${item.position || ''}</span>
                                            <span class="small text-muted fst-italic" style="font-size: 0.75rem;">${item.expertise || ''}</span>
                                        </div>
                                    </div>
                                </td>
                                
                                <td><span>${item.phone || '-'}</span></td>
                                
                                <td class="text-center">
                                    <button class="btn btn-sm btn-warning text-dark shadow-sm border-0" style="width: 32px; height: 32px;" onclick='editStaff(${JSON.stringify(item)})'>
                                        <i class="fa-solid fa-pen fa-xs"></i>
                                    </button>
                                    <button class="btn btn-sm btn-danger shadow-sm border-0 ms-1" style="width: 32px; height: 32px;" onclick="deleteStaff(${item.id})">
                                        <i class="fa-solid fa-trash fa-xs"></i>
                                    </button>
                                </td>
                            </tr>
                        `;
                    });
                    $('#table_staffs').html(html);
                }

                // Render nút phân trang
                renderPagination(res.pagination);
            }
        }
    });
}

// 4. Vẽ nút phân trang
function renderPagination(pg) {
    var html = '';
    
    // Nút Trước
    var prevDisabled = pg.has_prev ? '' : 'disabled';
    var prevPage = pg.has_prev ? pg.current_page - 1 : 1;
    
    html += `<li class="page-item ${prevDisabled}">
                <button class="page-link" onclick="loadStaffs(${prevPage})">Trước</button>
             </li>`;

    // Các số trang
    for (var i = 1; i <= pg.total_pages; i++) {
        var activeClass = (i === pg.current_page) ? 'active' : '';
        html += `<li class="page-item ${activeClass}">
                    <button class="page-link" onclick="loadStaffs(${i})">${i}</button>
                 </li>`;
    }

    // Nút Sau
    var nextDisabled = pg.has_next ? '' : 'disabled';
    var nextPage = pg.has_next ? pg.current_page + 1 : pg.total_pages;

    html += `<li class="page-item ${nextDisabled}">
                <button class="page-link" onclick="loadStaffs(${nextPage})">Sau</button>
             </li>`;

    $('#staff_pagination').html(html);
}

// --- CÁC HÀM THAO TÁC ---

function openStaffModal() {
    $('#staff_id').val('');
    $('#modalStaff input').val(''); 
    $('#modalStaff select').val(''); 
    $('#st_username').prop('readonly', false);
    $('#modalStaff').modal('show');
}

function editStaff(item) {
    $('#staff_id').val(item.id);
    
    $('#st_name').val(item.full_name);
    $('#st_phone').val(item.phone);
    $('#st_email').val(item.email);
    $('#st_username').val(item.username).prop('readonly', true);
    $('#st_password').val('');
    
    $('#st_role').val(item.role_id);
    $('#st_position').val(item.position_id);
    $('#st_expertise').val(item.expertise_id);
    $('#st_room').val(item.room_id);

    $('#modalStaff').modal('show');
}

function saveStaff() {
    var data = {
        id: $('#staff_id').val(),
        full_name: $('#st_name').val(),
        phone: $('#st_phone').val(),
        email: $('#st_email').val(),
        username: $('#st_username').val(),
        password: $('#st_password').val(),
        role_id: $('#st_role').val(),
        position_id: $('#st_position').val(),
        expertise_id: $('#st_expertise').val(),
        room_id: $('#st_room').val()
    };

    $.ajax({
        url: '/api/admin/staff/save',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(res) {
            if(res.success) {
                alert(res.message);
                $('#modalStaff').modal('hide');
                loadStaffs(currentStaffPage); // Load lại trang hiện tại
            } else {
                alert(res.message);
            }
        }
    });
}

function deleteStaff(id) {
    if(!confirm("Bạn có chắc muốn xóa nhân viên này?")) return;
    $.ajax({
        url: '/api/admin/staff/delete/' + id,
        type: 'DELETE',
        success: function(res) {
            if(res.success) {
                loadStaffs(currentStaffPage);
            } else {
                alert("Lỗi: " + res.message);
            }
        }
    });
}