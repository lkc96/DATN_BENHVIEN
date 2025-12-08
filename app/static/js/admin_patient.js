var currentPatientPage = 1; 
var currentKeyword = "";

$(document).ready(function() {
    loadPatients(1); 
    $('#patient_search').on('keypress', function(e) {
        if(e.which == 13) searchPatient();
    });
});

function searchPatient() {
    currentKeyword = $('#patient_search').val();
    loadPatients(1);
}

function loadPatients(page = 1) {
    currentPatientPage = page;

    $.ajax({
        url: '/api/admin/patients',
        type: 'GET',
        data: { page: page, keyword: currentKeyword },
        success: function(res) {
            if(res.success) {
                var html = '';
                if(!res.data || res.data.length === 0) {
                    $('#table_patients').html('<tr><td colspan="7" class="text-center py-5 text-muted fst-italic">Không tìm thấy dữ liệu</td></tr>');
                } else {
                    var startIndex = (res.pagination.current_page - 1) * 8;

                    $.each(res.data, function(i, item) {
                        
                        // Hiển thị trạng thái thẻ
                        var cardBadge = '';
                        if(item.card_code) {
                            var color = item.card_status === 'Active' ? 'success' : 'danger';
                            cardBadge = `<span class="badge bg-${color} text-white" style="font-size: 10px;">${item.card_code}</span>`;
                        } else {
                            cardBadge = `<span class="badge bg-secondary" style="font-size: 10px;">Chưa cấp</span>`;
                        }

                        // Hiển thị tài khoản
                        var accInfo = item.username ? `<div class="small text-primary fw-bold"><i class="fa-solid fa-user me-1"></i>${item.username}</div>` : '';

                        html += `
                            <tr>
                                <td class="text-center">${startIndex + i + 1}</td>
                                
                                <td>
                                    <a>
                                        ${item.full_name}
                                    </a>
                                </td>
                                
                                <td>
                                    <div>${item.card_code}</div>
                                </td>
                                
                                <td>
                                    ${item.date_birth ? formatDateVN(item.date_birth) : '-'}
                                    <br><small class="text-muted">${item.gender || ''}</small>
                                </td>
                                
                                <td>
                                    <div class="d-flex flex-column">
                                        <span >${item.phone || '-'}</span>
                                        <span class="small text-muted" style="font-size: 11px;">CCCD: ${item.id_number || '--'}</span>
                                    </div>
                                </td>
                                
                                <td><span class="small text-secondary">${item.address || ''}</span></td>
                                
                                <td class="text-center">
                                    <button class="btn btn-sm btn-warning text-dark shadow-sm border-0" style="width: 32px; height: 32px;" onclick='editPatient(${JSON.stringify(item)})'>
                                        <i class="fa-solid fa-pen fa-xs"></i>
                                    </button>
                                    <button class="btn btn-sm btn-danger shadow-sm border-0 ms-1" style="width: 32px; height: 32px;" onclick="deletePatient(${item.id})">
                                        <i class="fa-solid fa-trash fa-xs"></i>
                                    </button>
                                </td>
                            </tr>
                        `;
                    });
                    $('#table_patients').html(html);
                }
                renderPagination(res.pagination);
            }
        }
    });
}

function formatDateVN(dateString) {
    if(!dateString) return '';
    var p = dateString.split(/\D/);
    return [p[2], p[1], p[0]].join('/');
}

function renderPagination(pg) {
    var html = '';
    var prevDisabled = pg.has_prev ? '' : 'disabled';
    var prevPage = pg.has_prev ? pg.current_page - 1 : 1;
    html += `<li class="page-item ${prevDisabled}"><button class="page-link" onclick="loadPatients(${prevPage})">Trước</button></li>`;

    for (var i = 1; i <= pg.total_pages; i++) {
        var activeClass = (i === pg.current_page) ? 'active' : '';
        html += `<li class="page-item ${activeClass}"><button class="page-link" onclick="loadPatients(${i})">${i}</button></li>`;
    }

    var nextDisabled = pg.has_next ? '' : 'disabled';
    var nextPage = pg.has_next ? pg.current_page + 1 : pg.total_pages;
    html += `<li class="page-item ${nextDisabled}"><button class="page-link" onclick="loadPatients(${nextPage})">Sau</button></li>`;

    $('#patient_pagination').html(html);
}

// --- CRUD ---

function openPatientModal() {
    $('#patient_id').val('');
    $('#modalPatient input').val('');
    $('#pa_card_status').val('Active');
    $('#modalPatient').modal('show');
}

function editPatient(item) {
    $('#patient_id').val(item.id);
    
    // Info
    $('#pa_name').val(item.full_name);
    $('#pa_dob').val(item.date_birth); 
    $('#pa_gender').val(item.gender);
    $('#pa_phone').val(item.phone);
    $('#pa_id_number').val(item.id_number);
    $('#pa_address').val(item.address);
    
    // Account
    $('#pa_username').val(item.username);
    $('#pa_email').val(item.email);
    $('#pa_password').val('');
    
    // Card
    $('#pa_card_code').val(item.card_code);
    $('#pa_card_status').val(item.card_status);

    $('#modalPatient').modal('show');
}

function savePatient() {
    var data = {
        id: $('#patient_id').val(),
        full_name: $('#pa_name').val(),
        date_birth: $('#pa_dob').val(),
        gender: $('#pa_gender').val(),
        phone: $('#pa_phone').val(),
        id_number: $('#pa_id_number').val(),
        address: $('#pa_address').val(),
        
        username: $('#pa_username').val(),
        email: $('#pa_email').val(),
        password: $('#pa_password').val(),
        
        card_code: $('#pa_card_code').val(),
        card_status: $('#pa_card_status').val()
    };

    $.ajax({
        url: '/api/admin/patient/save',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(res) {
            if(res.success) {
                alert(res.message);
                $('#modalPatient').modal('hide');
                loadPatients(currentPatientPage);
            } else {
                alert(res.message);
            }
        },
        error: function(err) {
            alert("Lỗi: " + (err.responseJSON ? err.responseJSON.message : "Lỗi hệ thống"));
        }
    });
}

function deletePatient(id) {
    if(!confirm("Xóa hồ sơ bệnh nhân này? (Dữ liệu thẻ và tài khoản sẽ bị xóa theo)")) return;
    $.ajax({
        url: '/api/admin/patient/delete/' + id,
        type: 'DELETE',
        success: function(res) {
            if(res.success) {
                loadPatients(currentPatientPage);
            } else {
                alert(res.message);
            }
        }
    });
}