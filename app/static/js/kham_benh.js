var currentExamId = null;
var tempServices = [];
var allServicesCache = [];
var currentTicketServices = [];
var currentSubInvoiceIds = [];
var tempPrescription = [];

$(document).ready(function() {

    // 1. Khởi tạo lịch Flatpickr
    flatpickr("#filter_date", {
        dateFormat: "d/m/Y",
        defaultDate: "today",
        locale: "vn",
        mode: "range", 
        onChange: function(selectedDates, dateStr, instance) {
            loadExamList(1); // Load lại trang 1 khi chọn ngày
        }
    });

    // 2. Load danh sách lần đầu
    loadExamList(1);

    // 3. Sự kiện thay đổi phòng -> Load lại
    $('#filter_room').change(function() {
        loadExamList(1);
    });

    // Kích hoạt tìm kiếm cho ô Bệnh chính
    setupICDSearch('#icd_main_input', '#icd_main_list');
    
    // Kích hoạt tìm kiếm cho ô Bệnh phụ
    setupICDSearch('#icd_sub_input', '#icd_sub_list');

    loadAllServices();

    loadFunctionalRooms();

    // Sự kiện khi đổi Phiếu trong dropdown
    $('#cd_ticket_type').change(function() {
        var ticketCode = $(this).val();
        if(ticketCode === 'new') {
            // Nếu chọn "Thêm phiếu mới" -> Reset bảng, hiện lại các dịch vụ tạm
            renderServiceTable(); 
        } else {
            // Nếu chọn phiếu cũ -> Load từ DB
            loadServicesByTicket(ticketCode);
        }
    });

});

// Hàm tải danh sách chờ khám (Có tham số page)
function loadExamList(page = 1) {
    var tbody = $('#exam_table_body');
    tbody.html('<tr><td colspan="11" class="text-center py-5 text-muted"><i class="fa-solid fa-spinner fa-spin me-2"></i> Đang tải dữ liệu...</td></tr>');

    var roomId = $('#filter_room').val();
    var keyword = $('#filter_keyword').val();
    var dateRange = $('#filter_date').val();

    $.ajax({
        url: '/api/kham-benh/danh-sach-cho',
        type: 'GET',
        data: {
            room_id: roomId,
            keyword: keyword,
            date: dateRange,
            page: page // [QUAN TRỌNG] Gửi trang cần xem
        },
        success: function(response) {
            if (response.success) {
                tbody.empty();
                
                // Xử lý không có dữ liệu
                if (response.data.length === 0) {
                    tbody.html('<tr><td colspan="11" class="text-center py-4">Không có bệnh nhân nào đang chờ</td></tr>');
                    $('#info_count').text('0 bản ghi');
                    $('#pagination_links').empty(); // Xóa phân trang
                    return;
                }

                // Vẽ bảng dữ liệu
                $.each(response.data, function(index, item) {
                    // Highlight dòng đang khám
                    var rowClass = item.trang_thai.includes('Đang khám') ? 'table-warning' : ''; // table-warning sẽ ra màu vàng nhạt đẹp hơn
                    
                    var row = `
                        <tr class="align-middle ${rowClass} style="cursor: pointer;" 
                            onclick="startExamination(${item.exam_id})">
                            <td class="text-muted small">${item.ma_dk}</td>
                            <td>${item.thoi_gian}</td>
                            <td class="text-center fw-bold fs-5 text-primary">${item.stt}</td>
                            <td class="fw-bold text-uppercase">${item.ho_ten}</td>
                            <td class="text-muted">${item.ma_bn}</td>
                            <td class="text-center">${item.gioi_tinh || ''}</td>
                            <td class="text-center">${item.nam_sinh}</td>

                            <td class="small text-primary fw-bold">${item.phong_kham}</td>
                            <td class="text-center small">${item.trang_thai}</td>
                            <td class="text-center">
                                <button class="btn btn-sm btn-outline-primary rounded-circle" 
                                        title="Bắt đầu khám" 
                                        onclick="event.stopPropagation(); startExamination(${item.exam_id})">
                                    <i class="fa-solid fa-stethoscope"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                    tbody.append(row);
                });

                // [QUAN TRỌNG] Vẽ phân trang nếu có dữ liệu
                if (response.pagination) {
                    renderPagination(response.pagination);
                }
            }
        },
        error: function() {
            tbody.html('<tr><td colspan="11" class="text-center text-danger">Lỗi kết nối Server</td></tr>');
        }
    });
}

// Hàm vẽ phân trang
function renderPagination(pageData) {
    // A. Hiển thị thông tin số lượng
    var start = (pageData.current_page - 1) * pageData.per_page + 1;
    var end = start + pageData.per_page - 1;
    if (end > pageData.total_items) end = pageData.total_items;
    
    $('#info_count').text(`${start} - ${end} / ${pageData.total_items} bản ghi`);

    // B. Vẽ các nút bấm
    var html = '';
    var current = pageData.current_page;
    var total = pageData.total_pages;

    // Nút Previous
    if (current > 1) {
        html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="loadExamList(${current - 1})">«</a></li>`;
    } else {
        html += `<li class="page-item disabled"><a class="page-link" href="#">«</a></li>`;
    }

    // Các nút số trang (Chỉ hiện 5 trang xung quanh trang hiện tại)
    var startPage = Math.max(1, current - 2);
    var endPage = Math.min(total, current + 2);

    for (var i = startPage; i <= endPage; i++) {
        if (i === current) {
            html += `<li class="page-item active"><a class="page-link" href="#">${i}</a></li>`;
        } else {
            html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="loadExamList(${i})">${i}</a></li>`;
        }
    }

    // Nút Next
    if (current < total) {
        html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="loadExamList(${current + 1})">»</a></li>`;
    } else {
        html += `<li class="page-item disabled"><a class="page-link" href="#">»</a></li>`;
    }

    $('#pagination_links').html(html);
}

// Hàm chuyển sang màn hình khám lâm sàng
function startExamination(examId) {
    // Chuyển hướng sang trang chi tiết khám
    // window.location.href = '/kham-benh/chi-tiet/' + examId;
    alert("Bắt đầu khám cho phiếu ID: " + examId);
}

// 1. Hàm chuyển Tab
function switchTab(tabName) {
    if (tabName === 'danh-sach') {
        $('#view-danh-sach').show();     // Giả sử view danh sách cũ bạn bọc trong div id="view-danh-sach"
        $('#view-kham-lam-sang').hide();
        
        $('.nav-link').removeClass('active');
        $('.nav-link:contains("DANH SÁCH")').addClass('active');
        
        loadExamList(1); // Load lại danh sách
    } 
    else if (tabName === 'kham-lam-sang') {
        $('#view-danh-sach').hide();
        
        $('#view-kham-lam-sang').show();
        $('.nav-link').removeClass('active');
        $('.nav-link:contains("KHÁM LÂM SÀNG")').addClass('active');
    }
    
}

// 3. Hàm Bắt đầu khám (Logic chính)
function startExamination(examId) {
    currentExamId = examId; 
    $.ajax({
        url: '/api/kham-benh/bat-dau-kham',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ exam_id: examId }),
        success: function(res) {
            console.log(res.message); // Log chơi để biết
            
            // Nếu muốn danh sách bên ngoài cập nhật màu vàng ngay lập tức (tùy chọn)
            // loadExamList(1); 
        },
        error: function(err) {
            console.error("Không thể cập nhật trạng thái khám");
        }
    });
    
    $.ajax({
        url: '/api/kham-benh/chi-tiet/' + examId,
        type: 'GET',
        success: function(response) {
            if (response.success) {
                var data = response.data;
                var kham = data.kham_data || {}; // Dữ liệu khám cũ
                window.currentPatientId = data.patient_id;

                // 1. Điền Header Hành chính
                $('#kham_ma_bn').text(data.ma_bn);
                $('#kham_ho_ten').text(data.ho_ten);
                $('#kham_ngay_sinh').text(data.ngay_sinh);
                $('#kham_gioi_tinh').text(data.gioi_tinh);
                $('#kham_tuoi').text(data.tuoi);
                $('#kham_phong').text(data.phong_kham);
                $('#store_dia_chi').val(data.dia_chi);
                $('#store_bac_si').val(data.bac_si);
                // 2. [MỚI] Điền dữ liệu khám cũ (Nếu có)
                // Sinh hiệu
                $('#sh_can_nang').val(kham.weight);
                $('#sh_chieu_cao').val(kham.height);
                $('#sh_nhiet_do').val(kham.temperature);
                $('#sh_mach').val(kham.pulse);
                
                // Tách huyết áp (120/80) ra 2 ô
                if(kham.blood_pressure && kham.blood_pressure.includes('/')) {
                    var bp = kham.blood_pressure.split('/');
                    $('#sh_huyet_ap1').val(bp[0]);
                    $('#sh_huyet_ap2').val(bp[1]);
                } else {
                    $('#sh_huyet_ap1').val('');
                    $('#sh_huyet_ap2').val('');
                }
                
                $('#sh_bmi').val(kham.bmi);

                // Chẩn đoán
                $('#kham_ly_do').val(kham.clinical_symptoms || data.ly_do_kham); // Nếu chưa khám thì lấy lý do đăng ký
                $('#icd_main_input').val(kham.main_disease);
                $('#icd_sub_input').val(kham.sub_disease);
                $('#kham_huong_xu_ly').val(kham.treatment_plan);
                $('#kham_loi_dan').val(kham.doctor_advice);
                
                // Chuyển Tab
                switchTab('kham-lam-sang');
            }
        },
        error: function() { alert("Lỗi tải thông tin phiếu khám!"); }
    });
}

// CẬP NHẬT HÀM saveExamination
function saveExamination() {
    // Kiểm tra xem đang ở Tab nào
    // Giả sử: #panel-kham-lam-sang đang visible -> Lưu khám
    // #panel-chi-dinh đang visible -> Lưu chỉ định
    
    if ($('#panel-kham-lam-sang').is(':visible')) {
        // Gọi hàm lưu khám lâm sàng (Hàm cũ)
        saveClinicalDiagnosis(); 
    } 
    else if ($('#panel-chi-dinh').is(':visible')) {
        // Gọi hàm lưu chỉ định dịch vụ (Hàm mới)
        saveServiceAssignment();
    }
    else if ($('#panel-don-thuoc').is(':visible')) {
        // Gọi hàm lưu chỉ định dịch vụ (Hàm mới)
        savePrescription();
    }
}
// [MỚI] HÀM LƯU KẾT QUẢ KHÁM
function saveClinicalDiagnosis() {
    if (!currentExamId) {
        alert("Chưa chọn bệnh nhân để khám!");
        return;
    }

    // 1. Thu thập dữ liệu từ Form
    // (Lưu ý: Các ID này phải khớp với file HTML bạn đã tạo ở bài trước)
    var formData = {
        exam_id: currentExamId,
        
        // Sinh hiệu
        can_nang: $('#sh_can_nang').val(),
        chieu_cao: $('#sh_chieu_cao').val(),
        nhiet_do: $('#sh_nhiet_do').val(),
        mach: $('#sh_mach').val(),          // Bạn cần thêm id="sh_mach" vào HTML ô Mạch
        nhip_tho: $('#sh_nhip_tho').val(),  // Thêm id="sh_nhip_tho"
        huyet_ap: $('#sh_huyet_ap1').val() + '/' + $('#sh_huyet_ap2').val(), // Ghép tâm thu/trương
        spo2: $('#sh_spo2').val(),          // Thêm id="sh_spo2"
        bmi: parseFloat($('#sh_bmi').val()) || 0, // Chỉ lấy số

        // Chẩn đoán
        ly_do_kham: $('#kham_ly_do').val(),
        chan_doan_so_bo: $('#kham_chan_doan_so_bo').val(), // Thêm id vào textarea
        benh_chinh: $('#icd_main_input').val(),
        benh_phu: $('#icd_sub_input').val(),
        huong_xu_ly: $('#kham_xu_tri').val(), // Thêm id
        loi_dan: $('#kham_loi_dan').val(),         // Thêm id
        ngay_hen: $('#kham_ngay_hen').val(),
        // Khám
        benh_su: $('#kham_benh_su').val(),         // Thêm id
        tien_su: $('#kham_tien_su').val(),         // Thêm id
        kham_toan_than: $('#kham_toan_than').val() // Thêm id
    };

    // 2. Gửi API
    $.ajax({
        url: '/api/kham-benh/luu-chan-doan',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        success: function(response) {
            if (response.success) {
                // [THAY THẾ]
                showToast('success', "Lưu hồ sơ bệnh án thành công!");
                // alert(response.message); -> Xóa dòng này
            } else {
                showToast('error', response.message);
            }
        },
        error: function(err) {
            var msg = err.responseJSON ? err.responseJSON.message : "Lỗi kết nối";
            showToast('error', msg);
        }
    });
}
// 4. Tính chỉ số BMI
function calcBMI() {
    var weight = parseFloat($('#sh_can_nang').val());
    var heightCm = parseFloat($('#sh_chieu_cao').val());

    if (weight > 0 && heightCm > 0) {
        var heightM = heightCm / 100;
        var bmi = weight / (heightM * heightM);
        
        var status = "";
        if (bmi < 18.5) status = " (Gầy)";
        else if (bmi < 24.9) status = " (Bình thường)";
        else if (bmi < 29.9) status = " (Thừa cân)";
        else status = " (Béo phì)";

        $('#sh_bmi').val(bmi.toFixed(2) + status);
    } else {
        $('#sh_bmi').val('');
    }
}

// =========================================================
// HÀM TÌM KIẾM ICD-10 (AUTOCOMPLETE)
// =========================================================
function setupICDSearch(inputId, listId) {
    var timer; // Biến timer để delay (debounce) tránh gọi server liên tục

    $(inputId).on('input', function() {
        var keyword = $(this).val().trim();
        var $list = $(listId);

        // Xóa timer cũ nếu người dùng đang gõ tiếp
        clearTimeout(timer);

        if (keyword.length < 1) {
            $list.hide().empty();
            return;
        }

        // Đợi 300ms sau khi ngừng gõ mới gọi API
        timer = setTimeout(function() {
            $.ajax({
                url: '/api/icd10/search',
                type: 'GET',
                data: { keyword: keyword },
                success: function(response) {
                    $list.empty();
                    if (response.success && response.data.length > 0) {
                        $.each(response.data, function(i, item) {
                            // Tạo dòng gợi ý: [Mã] Tên bệnh
                            // Thêm onclick để chọn
                            var li = `
                                <li class="list-group-item list-group-item-action small py-2" 
                                    style="cursor: pointer;"
                                    onclick="selectICD('${inputId}', '${listId}', '${item.code}', '${item.name}')">
                                    <span class="fw-bold text-primary me-2">[${item.code}]</span> 
                                    <span>${item.name}</span>
                                </li>
                            `;
                            $list.append(li);
                        });
                        $list.show();
                    } else {
                        // Không tìm thấy
                        $list.html('<li class="list-group-item small text-muted fst-italic">Không tìm thấy bệnh phù hợp</li>').show();
                    }
                }
            });
        }, 300);
    });

    // Ẩn list khi click ra ngoài vùng chọn
    $(document).on('click', function(e) {
        if (!$(e.target).closest(inputId).length && !$(e.target).closest(listId).length) {
            $(listId).hide();
        }
    });
}

// Hàm chọn bệnh từ list và điền vào ô input
// Gán vào window để HTML gọi được
window.selectICD = function(inputId, listId, code, name) {
    // Điền dữ liệu vào ô input theo định dạng: "J00 - Viêm họng cấp"
    $(inputId).val(`${code} - ${name}`);
    
    // Ẩn danh sách gợi ý
    $(listId).hide();
};

// =========================================================
// LOGIC CHUYỂN TAB CON (Khám LS <-> Chỉ định)
// =========================================================
function switchSubTab(tabName) {
    // Reset active class menu
    $('#menu-kham-ls, #menu-chi-dinh, #menu-thu-tien, #menu-don-thuoc')
        .removeClass('active fw-bold text-primary bg-light')
        .addClass('text-dark');
    
    // Ẩn các panel
    $('#panel-kham-lam-sang, #panel-chi-dinh, #panel-thu-tien,#panel-don-thuoc').hide();

    if (tabName === 'kham-ls') {
        $('#panel-kham-lam-sang').show();
        $('#menu-kham-ls').addClass('active fw-bold text-primary bg-light').removeClass('text-dark');
    } 
    else if (tabName === 'chi-dinh') {
        $('#panel-chi-dinh').show();
        $('#menu-chi-dinh').addClass('active fw-bold text-primary bg-light').removeClass('text-dark');
        // Load danh sách đã chỉ định của bệnh nhân hiện tại
        loadAssignedServices();
    }
    else if (tabName === 'thu-tien') {
        $('#panel-thu-tien').show();
        $('#menu-thu-tien').addClass('active fw-bold text-primary bg-light').removeClass('text-dark');
        
        // GỌI HÀM TẢI HÓA ĐƠN
        loadSubInvoice();
    }
    else if (tabName === 'don-thuoc') {
        $('#panel-don-thuoc').show();
        $('#menu-don-thuoc').addClass('active fw-bold text-primary bg-light').removeClass('text-dark');
    
        if($('#dt_thuoc_id option').length <= 1) loadMedicines();
    }
}

// =========================================================
// LOGIC CHỈ ĐỊNH DỊCH VỤ
// =========================================================

// 1. Load dropdown dịch vụ
function loadAllServices() {
    $.ajax({
        url: '/api/dich-vu/all',
        type: 'GET',
        success: function(res) {
            if(res.success) {
                allServicesCache = res.data; 
                filterServiceDropdown();
            }
        }
    });
}
// 2. [CẬP NHẬT] Hàm lọc theo tên nhóm trong bảng CatalogServices
function filterServiceDropdown() {
    var showXN = $('#chk_xn').is(':checked');
    var showCDHA = $('#chk_cdha').is(':checked');
    var showPTTT = $('#chk_pttt').is(':checked');
    var showKhac = $('#chk_khac').is(':checked'); // Nếu bạn có checkbox "Khác"

    var filteredData = allServicesCache.filter(function(item) {
        // Chuyển tên nhóm về chữ thường để so sánh cho dễ
        var groupName = (item.catalog_name || '').toLowerCase();
        
        // LOGIC MAP TỪ TÊN NHÓM TRONG DB -> CHECKBOX
        
        // 1. Nhóm Xét nghiệm (XN)
        if (showXN && (groupName.includes('xét nghiệm') || groupName.includes('huyết học') || groupName.includes('sinh hóa') || groupName.includes('vi sinh'))) {
            return true;
        }
        
        // 2. Nhóm Chẩn đoán hình ảnh (CĐHA)
        if (showCDHA && (groupName.includes('chẩn đoán hình ảnh') || groupName.includes('siêu âm') || groupName.includes('chụp x quang') || groupName.includes('nội soi') || groupName.includes('chụp ct') || groupName.includes('mri'))) {
            return true;
        }
        
        // 3. Nhóm Phẫu thuật thủ thuật (PTTT)
        if (showPTTT && (groupName.includes('phẫu thuật') || groupName.includes('thủ thuật'))) {
            return true;
        }
        
        // 4. Nhóm Khác (Các nhóm còn lại nếu checkbox Khác được chọn)
        // (Nếu bạn không có checkbox Khác thì bỏ đoạn này)
        if (showKhac) {
            // Nếu không thuộc 3 nhóm trên thì cho hiện
            var isSpecial = groupName.includes('xét nghiệm') || groupName.includes('huyết học') || groupName.includes('sinh hóa') ||
                            groupName.includes('chẩn đoán') || groupName.includes('siêu âm') || groupName.includes('x-quang') ||
                            groupName.includes('phẫu thuật') || groupName.includes('thủ thuật');
            if (!isSpecial) return true;
        }

        return false;
    });

    // Vẽ lại Dropdown
    var html = '<option value="">-- Chọn dịch vụ --</option>';
    if (filteredData.length === 0) {
        html = '<option value="">-- Không có dịch vụ phù hợp --</option>';
    } else {
        $.each(filteredData, function(i, item) {
            html += `<option value="${item.id}" data-price="${item.price}">
                        ${item.name} (${item.catalog_name}) 
                     </option>`;
        });
    }
    
    $('#cd_service_id').html(html);
    
    // Reset giá tiền
    $('#cd_price').val(0);
}

// 3. Hàm chọn tất cả (Giữ nguyên)
function toggleAllFilters(source) {
    var isChecked = source.checked;
    $('#chk_xn, #chk_cdha, #chk_pttt, #chk_khac').prop('checked', isChecked);
    filterServiceDropdown();
}
// 2. Sự kiện chọn dịch vụ -> Hiện giá
$('#cd_service_id').change(function() {
    var price = $(this).find(':selected').data('price') || 0;
    var fmt = new Intl.NumberFormat('vi-VN').format(price);
    $('#cd_price').val(fmt);
});


// 1. LOGIC THÊM TẠM VÀO BẢNG (CLIENT SIDE)
function addServiceOrder() {
    // Chỉ cho phép thêm khi đang ở chế độ "Thêm phiếu mới"
    if ($('#cd_ticket_type').val() !== 'new') {
        alert("Vui lòng chọn 'Thêm phiếu mới' để chỉ định thêm dịch vụ!");
        $('#cd_ticket_type').val('new').trigger('change');
        return;
    }

    var serviceId = $('#cd_service_id').val();
    var serviceName = $('#cd_service_id option:selected').text();
    var price = $('#cd_service_id option:selected').data('price');
    var qty = $('#cd_qty').val();
    // [MỚI] Lấy thông tin phòng
    var roomId = $('#cd_room_id').val();
    var roomName = $('#cd_room_id option:selected').text();

    if (!serviceId) { alert("Vui lòng chọn dịch vụ!"); return; }
    if (!roomId) { alert("Vui lòng chọn phòng thực hiện!"); return; }
    // Thêm vào mảng tạm
    tempServices.push({
        service_id: serviceId,
        service_name: serviceName,
        room_id: roomId,       // Lưu ID để gửi server
        room_name: roomName,
        price: price,
        quantity: qty,
        total: price * qty
    });

    // Vẽ lại bảng
    renderServiceTable();
}

// Hàm vẽ bảng (Kết hợp dữ liệu Tạm)
function renderServiceTable() {
    var tbody = $('#cd_table_body');
    tbody.empty();
    var totalAmount = 0;

    // Duyệt mảng tạm để vẽ
    $.each(tempServices, function(i, item) {
        var priceFmt = new Intl.NumberFormat('vi-VN').format(item.price);
        var totalFmt = new Intl.NumberFormat('vi-VN').format(item.total);
        totalAmount += item.total;

        var row = `
            <tr class="table-warning"> <td class="text-center">${i + 1}</td>
                <td>${item.service_name} <span class="badge bg-warning text-dark ms-2">Mới</span></td>
                <td class="text-primary small fw-bold">${item.room_name}</td>
                <td class="text-center">${item.quantity}</td>
                <td class="text-end">${priceFmt}</td>
                <td class="text-end fw-bold">${totalFmt}</td>
                <td class="text-center">Chờ thực hiện</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-danger border-0" onclick="removeTempService(${i})">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </td>
            </tr>
        `;
        tbody.append(row);
    });

    $('#cd_total_amount').text(new Intl.NumberFormat('vi-VN').format(totalAmount) + " đ");
    $('#cd_total_count').text(tempServices.length);
}

// Xóa khỏi mảng tạm
function removeTempService(index) {
    tempServices.splice(index, 1);
    renderServiceTable();
}

// =========================================================
// 2. LOGIC LƯU VÀO CSDL (KHI BẤM NÚT LƯU Ở TAB CHỈ ĐỊNH)
// =========================================================
function saveServiceAssignment() {
    if (tempServices.length === 0) {
        alert("Danh sách chỉ định trống! Vui lòng thêm dịch vụ.");
        return;
    }

    $.ajax({
        url: '/api/kham-benh/luu-chi-dinh',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            exam_id: currentExamId,
            services: tempServices
        }),
        success: function(res) {
            if (res.success) {
                showToast('success', res.message);
                tempServices = []; // Xóa mảng tạm
                loadTicketDropdown(); // Tải lại danh sách phiếu
                // Tự động chọn phiếu vừa tạo để xem
                // loadServicesByTicket(res.ticket_code);
                if(res.tickets && res.tickets.length > 0) {
                    var firstTicket = res.tickets[0];
                    // Đợi 1 xíu để dropdown kịp render (hoặc set value trực tiếp sau khi load xong)
                    setTimeout(function() {
                        $('#cd_ticket_type').val(firstTicket).trigger('change');
                    }, 500);
                } else {
                    // Nếu ko có phiếu (lỗi logic) thì reset về new
                    renderServiceTable();
                }
            } else {
                showToast('error', res.message);
            }
        },
        error: function(err) { showToast('error', "Lỗi kết nối Server"); }
    });
}

// =========================================================
// 3. LOGIC LOAD DỮ LIỆU TỪ DB
// =========================================================

// Load Dropdown Phiếu
function loadTicketDropdown() {
    $.ajax({
        url: '/api/kham-benh/danh-sach-phieu/' + currentExamId,
        type: 'GET',
        success: function(res) {
            var html = '<option value="new">Thêm phiếu mới</option>';
            if(res.success) {
                $.each(res.data, function(i, item) {
                    html += `<option value="${item.code}">${item.name}</option>`;
                });
            }
            $('#cd_ticket_type').html(html);
        }
    });
}

// Load Dịch vụ của Phiếu cũ
function loadServicesByTicket(ticketCode) {
    $.ajax({
        url: '/api/kham-benh/chi-tiet-phieu',
        type: 'GET',
        data: { exam_id: currentExamId, ticket_code: ticketCode },
        success: function(res) {
            var tbody = $('#cd_table_body');
            tbody.empty();
            if(res.success) {
                currentTicketServices = res.data;
                $.each(res.data, function(i, item) {
                    var priceFmt = new Intl.NumberFormat('vi-VN').format(item.price);
                    var totalFmt = new Intl.NumberFormat('vi-VN').format(item.total);
                    
                    var row = `
                        <tr>
                            <td class="text-center">${i + 1}</td>
                            <td class="fw-bold text-primary">${item.service_name}</td>
                            <td class="text-center">${item.quantity}</td>
                            <td class="text-end">${priceFmt}</td>
                            <td class="text-end fw-bold">${totalFmt}</td>
                            <td>${item.status == 'Chờ thực hiện'}</td>
                            <td>Đã lưu</td>
                            <td class="text-center">
                                <button class="btn btn-sm btn-outline-danger border-0" onclick="deleteServiceOrder(${item.order_id})">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                    tbody.append(row);
                });
                $('#cd_total_amount').text(new Intl.NumberFormat('vi-VN').format(res.total_amount) + " đ");
            }
        }
    });
}

// 3. Load bảng dịch vụ đã chỉ định
function loadAssignedServices() {
    if (!currentExamId) return; // currentExamId lấy t logic khám bệnh cũ

    $.ajax({
        url: '/api/kham-benh/dich-vu-da-chon/' + currentExamId,
        type: 'GET',
        success: function(res) {
            if(res.success) {
                var tbody = $('#cd_table_body');
                tbody.empty();
                
                $.each(res.data, function(i, item) {
                    var priceFmt = new Intl.NumberFormat('vi-VN').format(item.price);
                    var totalFmt = new Intl.NumberFormat('vi-VN').format(item.total);
                    
                    var row = `
                        <tr class="align-middle">
                            <td class="text-center">${i+1}</td>
                            <td class="fw-bold text-primary">${item.service_name}</td>
                            <td class="text-center">${item.quantity}</td>
                            <td class="text-end">${priceFmt}</td>
                            <td class="text-end fw-bold">${totalFmt}</td>
                            <td>${item.status}</td>  
                            <td class="text-center">
                                <button class="btn btn-sm btn-outline-danger border-0" onclick="deleteServiceOrder(${item.order_id})">
                                    <i class="fa-solid fa-trash"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                    tbody.append(row);
                });

                // Cập nhật Footer
                $('#cd_total_count').text(res.total_count);
                var totalAllFmt = new Intl.NumberFormat('vi-VN').format(res.total_amount);
                $('#cd_total_amount').text(totalAllFmt);
            }
        }
    });
}

// 5. Xóa chỉ định
function deleteServiceOrder(orderId) {
    if(!confirm("Bạn muốn xóa dịch vụ này?")) return;
    
    $.ajax({
        url: '/api/kham-benh/xoa-dich-vu/' + orderId,
        type: 'DELETE',
        success: function(res) {
            if(res.success) loadAssignedServices();
            else alert(res.message);
        }
    });
}


// =========================================================
// LOGIC IN PHIẾU CHỈ ĐỊNH (ĐÃ SỬA: LẤY STT THẬT TỪ API)
// =========================================================

// Hàm 1: Kiểm tra và gọi API lấy số
function printServiceOrder() {
    var ticketCode = $('#cd_ticket_type').val();
    
    // Validate dữ liệu
    if (ticketCode === 'new' || !ticketCode) {
        alert("Vui lòng chọn một phiếu đã lưu để in!");
        return;
    }
    
    if (typeof currentTicketServices === 'undefined' || currentTicketServices.length === 0) {
        alert("Phiếu này trống!");
        return;
    }

    // --- BẮT ĐẦU SỬA: GỌI AJAX LẤY STT ---
    // Hiển thị loading nhẹ (nếu muốn) hoặc disable nút in để tránh bấm nhiều lần
    
    $.ajax({
        url: '/api/kham-benh/lay-stt-in', // Gọi API Python vừa viết
        type: 'GET',
        data: { ticket_code: ticketCode },
        success: function(response) {
            // Lấy dữ liệu thật từ Server trả về
            // Nếu API báo lỗi hoặc không có số, ta để STT là rỗng hoặc 1 tùy ý
            var realSTT = (response && response.success) ? response.stt : ''; 
            var realRoomName = (response && response.success && response.room_name) ? response.room_name : "";

            // Gọi hàm thực hiện in với dữ liệu thật
            executePrint(ticketCode, realSTT, realRoomName);
        },
        error: function(err) {
            console.error(err);
            alert("Không kết nối được server để lấy số thứ tự! Sẽ in với STT trống.");
            // Vẫn cho in nhưng STT để trống
            executePrint(ticketCode, '', ''); 
        }
    });
}

// Hàm 2: Thực hiện vẽ mẫu in và mở cửa sổ (Được tách ra để gọi sau khi có API)
function executePrint(ticketCode, stt, dbRoomName) {
    // currentExamId là biến toàn cục
    var maDK = "DK" + String(currentExamId).padStart(9, '0');
    
    // 1. XÁC ĐỊNH TIÊU ĐỀ & PHÒNG THỰC HIỆN
    var title = "PHIẾU CHỈ ĐỊNH DỊCH VỤ";
    
    // Ưu tiên lấy tên phòng từ Database trả về. 
    // Nếu DB không trả về (lỗi), dùng logic cũ để đoán tên phòng.
    var roomExecute = dbRoomName; 

    if (!roomExecute) {
        if (ticketCode.startsWith("XN")) {
            roomExecute = "Phòng Xét Nghiệm";
        } else if (ticketCode.startsWith("CDHA")) {
            roomExecute = "Phòng X-Quang / Siêu Âm";
        } else if (ticketCode.startsWith("PTTT")) {
            roomExecute = "Phòng Thủ Thuật";
        } else {
            roomExecute = "Phòng chức năng";
        }
    }

    // Xác định Tiêu đề dựa trên mã phiếu
    if (ticketCode.startsWith("XN")) {
        title = "PHIẾU YÊU CẦU XÉT NGHIỆM";
    } else if (ticketCode.startsWith("CDHA")) {
        title = "PHIẾU CHẨN ĐOÁN HÌNH ẢNH";
    } else if (ticketCode.startsWith("PTTT")) {
        title = "PHIẾU PHẪU THUẬT THỦ THUẬT";
    }

    // 2. CHUẨN BỊ DỮ LIỆU
    var data = {
        ma_bn: $('#kham_ma_bn').text(),
        ma_dk: maDK,
        ma_phieu: ticketCode,
        title: title,
        phong_thuc_hien: roomExecute,
        ho_ten: $('#kham_ho_ten').text(),
        nam_sinh: $('#kham_ngay_sinh').text(),
        gioi_tinh: $('#kham_gioi_tinh').text(),
        dia_chi: $('#store_dia_chi').val(),
        chan_doan: $('#kham_chan_doan_so_bo').val() + ' ' + $('#icd_main_input').val(),
        bac_si: $('#store_bac_si').val(),
        
        // --- SỬ DỤNG STT THẬT TỪ API ---
        stt: stt 
    };

    // 3. MỞ CỬA SỔ IN (CẤU HÌNH CSS MỚI)
    var win = window.open('', '', 'height=800,width=1000');
    
    // Lấy mẫu HTML
    var templateArea = document.getElementById('print-service-area');
    var template = templateArea ? templateArea.innerHTML : "<h1>Lỗi: Không tìm thấy mẫu in</h1>";
    
    win.document.write('<html><head><title>In Phiếu</title>');
    
    // --- CSS QUAN TRỌNG ĐỂ FULL KHỔ GIẤY ---
    win.document.write('<style>');
    win.document.write(`
        @page { size: A4; margin: 10mm; } /* Căn lề 10mm cho tiết kiệm giấy */
        body { 
            font-family: 'Times New Roman', serif; 
            margin: 0; 
            padding: 0;
        }
        .print-container { 
            width: 100%;       
            max-width: 100%;   
            box-sizing: border-box;
        }
        table { width: 100%; border-collapse: collapse; } 
        th, td { border: 1px solid #000; padding: 6px; }
        
        /* Căn chỉnh header */
        .header-flex { display: flex; justify-content: space-between; align-items: flex-start; }
        .barcode-box { text-align: right; min-width: 250px; } 
        
        /* CSS cho số STT to rõ */
        .stt-box { font-size: 24px; font-weight: bold; border: 2px solid #000; padding: 5px 10px; display: inline-block; }
    `);
    win.document.write('</style>');
    
    // Nhúng thư viện barcode
    win.document.write('<script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"><\/script>');
    win.document.write('</head><body>');
    
    // Bọc nội dung vào container
    win.document.write('<div class="print-container">');
    win.document.write(template);
    win.document.write('</div>');
    
    win.document.write('</body></html>');
    
    // 4. ĐIỀN DỮ LIỆU VÀO CỬA SỔ MỚI (DOM CỦA WIN)
    var doc = win.document;
    
    // Helper check null để tránh lỗi JS nếu ID không tồn tại
    function setText(id, val) {
        var el = doc.getElementById(id);
        if(el) el.innerText = val || '';
    }

    setText('p_sv_madk_top', data.ma_dk);
    setText('p_sv_title', data.title);
    setText('p_sv_phong_thuc_hien', $('#kham_phong').text()); // Phòng khám chỉ định
    setText('p_sv_mabn_text', data.ma_bn);
    setText('p_sv_maphieu_text', data.ma_phieu);
    
    // Điền STT và Phòng thực hiện (QUAN TRỌNG)
    setText('p_sv_stt', data.stt); 
    setText('p_sv_phong_thuc_hien_box', data.phong_thuc_hien);

    // Hành chính
    setText('p_sv_hoten', data.ho_ten);
    setText('p_sv_namsinh', data.nam_sinh);
    setText('p_sv_gioitinh', data.gioi_tinh);
    setText('p_sv_diachi', data.dia_chi);
    setText('p_sv_chandoan', data.chan_doan);
    setText('p_sv_bacsi', data.bac_si);
    setText('p_sv_bs_ky', data.bac_si);

    // Ngày tháng
    var now = new Date();
    setText('p_sv_ngay', now.getDate());
    setText('p_sv_thang', now.getMonth() + 1);
    setText('p_sv_nam', now.getFullYear());

    // Bảng dịch vụ
    var tbody = doc.getElementById('p_sv_tbody');
    if (tbody) {
        tbody.innerHTML = ''; // Xóa mẫu
        $.each(currentTicketServices, function(i, item) {
            var row = `<tr>
                <td style="border: 1px solid #000; text-align: center; padding: 5px;">${i+1}</td>
                <td style="border: 1px solid #000; padding: 5px;"><b>${item.service_name}</b></td>
                <td style="border: 1px solid #000; text-align: center; padding: 5px;">${item.quantity}</td>
                <td style="border: 1px solid #000; padding: 5px;">${item.description || ''}</td>
            </tr>`;
            tbody.innerHTML += row;
        });
    }

    win.document.close();
    win.focus();

    // 5. TẠO MÃ VẠCH VÀ IN
    setTimeout(function() {
        if(win.JsBarcode) {
            try {
                // --- BARCODE GÓC PHẢI (MÃ ĐK) ---
                if (doc.getElementById("barcode_dk_top")) {
                    win.JsBarcode("#barcode_dk_top", data.ma_dk, {
                        format: "CODE128", width: 1.5, height: 35, displayValue: false, margin: 0
                    });
                }

                // --- BARCODE GÓC TRÁI (MÃ PHIẾU) ---
                if (doc.getElementById("barcode_phieu")) {
                    win.JsBarcode("#barcode_phieu", data.ma_phieu, {
                        format: "CODE128", width: 1.3, height: 35, displayValue: false, margin: 0
                    });
                }
                
                win.print();
                win.close();
            } catch (e) {
                console.warn("Lỗi tạo barcode:", e);
                win.print(); // Vẫn in dù lỗi barcode
            }
        } else {
            console.warn("Thư viện JsBarcode chưa tải xong");
            win.print();
        }
    }, 800);
}

// Gán vào window
window.printServiceOrder = printServiceOrder;

window.printGlobal = function() {
    // Kiểm tra đang ở tab nào
    if ($('#panel-kham-lam-sang').is(':visible')) {
        // In phiếu khám bệnh / Toa thuốc (Sẽ làm sau)
        alert("Chức năng in Toa thuốc đang phát triển");
    } 
    else if ($('#panel-chi-dinh').is(':visible')) {
        // In phiếu chỉ định
        printServiceOrder();
    }
    else if ($('#panel-don-thuoc').is(':visible')) {
        // In phiếu chỉ định
        printPrescriptionFunc();
    }
};

// B. HÀM TẢI HÓA ĐƠN (TAB THU TIỀN)
function loadSubInvoice() {
    currentSubInvoiceIds = [];
    if (!window.currentPatientId) {
        alert("Chưa có thông tin bệnh nhân!");
        return;
    }

    // Reset giao diện
    $('#sub_bill_body').html('');
    $('#sub_pay_total').val('0');
    $('#sub_bill_total').text('0');
    $('#sub_qr_img').hide();
    $('#sub_qr_icon').show();
    
    // Ngày hiện tại
    var now = new Date();
    $('#pay_date_sub').val(now.getDate() + '/' + (now.getMonth()+1) + '/' + now.getFullYear() + ' ' + now.getHours() + ':' + now.getMinutes());

    // Gọi API lấy hóa đơn (Dùng chung API với bên Tiếp đón)
    $.ajax({
        url: '/api/kham-benh/hoa-don/' + window.currentPatientId,
        type: 'GET',
        success: function(response) {
            if (response.success) {
                var data = response.data;
                currentSubInvoiceIds = data.invoice_ids; // Lưu mảng ID hóa đơn

                // 1. Điền Header
                $('#bill_ma_bn').text(data.ma_bn);
                $('#bill_ho_ten').text(data.ho_ten);
                $('#bill_ngay_sinh').text(data.ngay_sinh);
                $('#bill_gioi_tinh').text(data.gioi_tinh);
                $('#bill_tuoi').text(data.tuoi);
                $('#bill_phong_kham').text(data.phong_kham);
                $('#bill_bac_si').text(data.bac_si);
                $('#bill_trang_thai').text("Chờ thanh toán");

                // 2. Hiển thị QR (Góc trái trên)
                if(data.qr_url) {
                    $('#sub_qr_img').attr('src', data.qr_url).show();
                    $('#sub_qr_icon').hide();
                }

                // 3. Vẽ Bảng dịch vụ
                var total = 0;
                $.each(data.details, function(i, item) {
                    var priceFmt = new Intl.NumberFormat('vi-VN').format(item.unit_price);
                    var totalFmt = new Intl.NumberFormat('vi-VN').format(item.total);
                    
                    var row = `<tr>
                        <td class="text-center"><input type="checkbox" checked disabled></td>
                        <td class="fw-bold text-dark">${item.service_name}</td>
                        <td class="text-center">Lần</td>
                        <td class="text-center">${item.quantity}</td>
                        <td class="text-end">${priceFmt}</td>
                        <td class="text-end fw-bold">${totalFmt}</td>
                    </tr>`;
                    $('#sub_bill_body').append(row);
                    total += item.total;
                });

                // 4. Cập nhật Tổng tiền
                var finalTotal = new Intl.NumberFormat('vi-VN').format(total);
                $('#sub_bill_total').text(finalTotal);
                $('#sub_pay_total').val(finalTotal);

            } else {
                // Reset bảng khi không có hóa đơn
                currentSubInvoiceIds = [];
                $('#sub_bill_body').html('<tr><td colspan="6" class="text-center text-muted fst-italic py-5">Không có dịch vụ cần thanh toán</td></tr>');
            }
        }
    });
}

// 2. Hàm thanh toán
function submitSubPayment() {
    console.log("Đang gửi thanh toán IDs:", currentSubInvoiceIds);

    if (!currentSubInvoiceIds || currentSubInvoiceIds.length === 0) {
        alert("Không có hóa đơn nào để thanh toán!");
        return;
    }

    if(!confirm("Xác nhận thu tiền?")) return;

    $.ajax({
        url: '/api/kham-benh/thanh-toan',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            invoice_ids: currentSubInvoiceIds, // Gửi mảng ID
            payment_method: $('#sub_pay_method').val()
        }),
        success: function(response) {
            if (response.success) {
                alert("THANH TOÁN THÀNH CÔNG!");
                loadSubInvoice(); // Reload lại
            } else {
                alert(response.message);
            }
        },
        error: function(err) { 
            // In lỗi chi tiết từ server trả về nếu có
            var msg = err.responseJSON ? err.responseJSON.message : "Lỗi kết nối";
            alert("Lỗi: " + msg); 
        }
    });
}

// 1. HÀM LOAD DANH SÁCH THUỐC (Bỏ giá/stock)
function loadMedicines() {
    $.ajax({
        url: '/api/thuoc/all',
        type: 'GET',
        success: function(res) {
            if(res.success) {
                var html = '<option value="">-- Chọn thuốc --</option>';
                $.each(res.data, function(i, m) {
                    // Chỉ lưu đơn vị vào data
                    html += `<option value="${m.id}" data-unit="${m.unit}">${m.name}</option>`;
                });
                $('#dt_thuoc_id').html(html);
            }
        }
    });
}

// Sự kiện chọn thuốc -> Điền ĐVT
$('#dt_thuoc_id').change(function() {
    var opt = $(this).find(':selected');
    $('#dt_dvt').val(opt.data('unit'));
    $('#dt_so_luong').focus(); // Nhảy sang ô số lượng
});
// Gắn sự kiện 'input' cho các ô nhập liệu
$('#dt_sang, #dt_trua, #dt_chieu, #dt_toi, #dt_so_ngay').on('input', function() {
    calculateTotalQty();
});

function calculateTotalQty() {
    // Lấy giá trị, nếu rỗng coi là 0
    var sang = parseInt($('#dt_sang').val()) || 0;
    var trua = parseInt($('#dt_trua').val()) || 0;
    var chieu = parseInt($('#dt_chieu').val()) || 0;
    var toi = parseInt($('#dt_toi').val()) || 0;
    
    var soNgay = parseInt($('#dt_so_ngay').val()) || 1; // Mặc định 1 ngày

    // Công thức: (Tổng liều 1 ngày) * Số ngày
    var tongLieuNgay = sang + trua + chieu + toi;
    var tongCap = tongLieuNgay * soNgay;

    // Gán vào ô Tổng cấp
    $('#dt_so_luong').val(tongCap);
}
// 2. THÊM VÀO BẢNG TẠM
window.addMedicineToTable = function() {
    var id = $('#dt_thuoc_id').val();
    if(!id) { alert("Chưa chọn thuốc!"); return; }
    
    var name = $('#dt_thuoc_id option:selected').text();
    var unit = $('#dt_dvt').val();
    var qty = $('#dt_so_luong').val();
    
    if(parseInt(qty) <= 0) { alert("Số lượng phải lớn hơn 0"); return; }

    tempPrescription.push({
        id: id,
        name: name,
        unit: unit,
        sang: $('#dt_sang').val(),
        trua: $('#dt_trua').val(),
        chieu: $('#dt_chieu').val(),
        toi: $('#dt_toi').val(),
        so_ngay: $('#dt_so_ngay').val(),     // Gửi số ngày lên server (nếu cần xử lý thêm)
        so_luong: qty,                       // Gửi tổng số lượng
        cach_dung_them: $('#dt_cach_dung').val()
    });

    renderPrescriptionTable();
    
    // Reset form nhập nhanh
    $('.dt-lieu').val('');
    $('#dt_so_luong').val('1');
    $('#dt_cach_dung').val('');
    $('#dt_thuoc_id').val('').trigger('change');
    $('#dt_thuoc_id').focus();
};

// 3. VẼ BẢNG THUỐC (Không có cột tiền)
function renderPrescriptionTable() {
    var tbody = $('#dt_table_body');
    tbody.empty();
    
    $.each(tempPrescription, function(i, item) {
        // --- [SỬA ĐOẠN NÀY] TẠO CHUỖI CÁCH DÙNG HIỂN THỊ ---
        var hdsdParts = [];
        
        // Kiểm tra từng buổi, nếu có số lượng thì thêm vào chuỗi
        if(item.sang && item.sang > 0) hdsdParts.push(`Sáng ${item.sang}`);
        if(item.trua && item.trua > 0) hdsdParts.push(`Trưa ${item.trua}`);
        if(item.chieu && item.chieu > 0) hdsdParts.push(`Chiều ${item.chieu}`);
        if(item.toi && item.toi > 0) hdsdParts.push(`Tối ${item.toi}`);
        
        // Ghép lại bằng dấu phẩy. VD: "Sáng 1, Tối 1"
        var hdsdString = hdsdParts.join(', ');
        
        // Nếu có ghi chú thêm thì nối vào. VD: "Sáng 1 (Uống sau ăn)"
        if(item.cach_dung_them) {
            if(hdsdString) hdsdString += ` (${item.cach_dung_them})`;
            else hdsdString = item.cach_dung_them;
        }
        
        // Mặc định nếu không có gì
        if(!hdsdString) hdsdString = "-";
        // ----------------------------------------------------

        var row = `
            <tr class="align-middle">
                <td class="text-center">${i+1}</td>
                <td class="fw-bold text-primary">${item.name}</td>
                <td class="text-center">${item.unit}</td>
                
                <td>${hdsdString}</td>
                
                <td class="text-center fw-bold text-danger">${item.so_luong}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-danger border-0" onclick="removeMedicine(${i})">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

window.removeMedicine = function(index) {
    tempPrescription.splice(index, 1);
    renderPrescriptionTable();
};

// 4. LƯU ĐƠN THUỐC
function savePrescription() {
    if (tempPrescription.length === 0) {
        alert("Đơn thuốc trống!");
        return;
    }
    if (!confirm("Lưu đơn thuốc này?")) return;

    var data = {
        exam_id: currentExamId,
        medicines: tempPrescription,
        loi_dan: $('#dt_loi_dan').val()
    };

    $.ajax({
        url: '/api/kham-benh/luu-don-thuoc',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(res) {
            if(res.success) {
                showToast('success', res.message);
            } else {
                showToast('error', res.message);
            }
        },
        error: function(err) { showToast('error', "Lỗi kết nối Server"); }
    });
}

// 1. HÀM LOAD PHÒNG CHỨC NĂNG
function loadFunctionalRooms() {
    $.ajax({
        url: '/api/phong/chuc-nang',
        type: 'GET',
        success: function(res) {
            if(res.success) {
                var html = '<option value="">-- Chọn phòng --</option>';
                $.each(res.data, function(i, item) {
                    html += `<option value="${item.id}">${item.name}</option>`;
                });
                $('#cd_room_id').html(html);
            }
        }
    });
}

// HÀM IN ĐƠN THUỐC
// Hàm In đơn thuốc
function printPrescriptionFunc() {
    if (!currentExamId) { alert("Chưa chọn bệnh nhân!"); return; }

    // Gọi API lấy dữ liệu
    $.ajax({
        url: '/api/kham-benh/in-don-thuoc/' + currentExamId,
        type: 'GET',
        success: function(res) {
            if (res.success) {
                var data = res.data;
                
                // 1. Điền Thông tin Hành chính
                $('#p_so_y_te').text(data.so_y_te);
                $('#p_ten_bv').text(data.ten_bv);
                $('#p_dia_chi_bv').text(data.dia_chi_bv);
                $('#p_sdt_bv').text(data.sdt_bv);
                
                $('#p_ma_bn_header').text(data.ma_bn);
                $('#p_ma_don').text(data.ma_don);
                
                $('#p_ho_ten').text(data.ho_ten);
                $('#p_ma_bn').text(data.ma_bn);
                $('#p_cccd').text(data.cccd);
                $('#p_gioi_tinh').text(data.gioi_tinh);
                $('#p_ngay_sinh').text(data.ngay_sinh);
                $('#p_can_nang').text(data.can_nang);
                $('#p_the_bhyt').text(data.the_bhyt);
                $('#p_dia_chi').text(data.dia_chi);
                
                $('#p_chan_doan').text(data.chan_doan);

                // 2. Điền Danh sách thuốc (Vòng lặp)
                var htmlThuoc = '';
                if(data.thuoc && data.thuoc.length > 0) {
                    $.each(data.thuoc, function(i, item) {
                        // [XỬ LÝ HIỂN THỊ TÊN THUỐC]
                        // Format: Hoạt chất + Hàm lượng + (Tên thuốc in đậm)
                        // VD: Paracetamol 500mg (Panadol)
                        
                        var tenHienThi = '';
                        
                        // 1. Thêm Hoạt chất (nếu có)
                        if(item.hoat_chat) tenHienThi += item.hoat_chat + ' ';
                        
                        // 2. Thêm Hàm lượng (nếu có)
                        if(item.ham_luong) tenHienThi += item.ham_luong + ' ';
                        
                        // 3. Thêm Tên thuốc (In đậm trong ngoặc)
                        // Nếu chưa có hoạt chất thì hiển thị tên thuốc in đậm không ngoặc (cho đẹp)
                        if(tenHienThi.trim() === '') {
                             tenHienThi = `<strong>${item.ten_thuoc}</strong>`;
                        } else {
                             tenHienThi += `(<strong>${item.ten_thuoc}</strong>)`;
                        }
                        htmlThuoc += `
                            <li class="row mb-2">
                                <div class="col-9">
                                    <strong style="font-size: 16px;">${item.stt}. </strong>
                                    <strong style="font-size: 16px;">${tenHienThi}</strong><br/>
                                    <span style="font-style: italic;">${item.cach_dung}</span>
                                </div>
                                <div class="col-3 text-end">
                                    <strong>${item.so_luong} ${item.dvt}</strong>
                                </div>
                            </li>
                        `;
                    });
                } else {
                    htmlThuoc = '<p class="text-center fst-italic">Không có thuốc</p>';
                }
                $('#p_list_thuoc').html(htmlThuoc);

                // 3. Điền thông tin Dinh dưỡng & Lời dặn
                $('#p_sl_can_nang').text(data.can_nang);
                $('#p_sl_chieu_cao').text(data.chieu_cao);
                $('#p_sl_bmi').text(data.bmi);
                
                // Logic đánh giá BMI đơn giản
                var bmiStatus = "TTDD bình thường";
                if(data.bmi < 18.5) bmiStatus = "Gầy";
                else if(data.bmi >= 25) bmiStatus = "Thừa cân";
                $('#p_ket_luan_dinh_duong').text(bmiStatus);

                $('#p_loi_dan').text(data.loi_dan);
                $('#p_ngay_tai_kham').text(data.ngay_tai_kham || "...........");
                
                // 4. Footer
                $('#p_ngay_in').text(data.ngay_in_ngay);
                $('#p_thang_in').text(data.ngay_in_thang);
                $('#p_nam_in').text(data.ngay_in_nam);
                $('#p_bac_si').text(data.bac_si);

                // 5. Mở cửa sổ in
                var content = document.getElementById('print-prescription-template').innerHTML;
                
                // Thêm CSS Bootstrap vào cửa sổ in để không bị vỡ layout
                var win = window.open('', '', 'height=800,width=1000');
                win.document.write('<html><head><title>IN ĐƠN THUỐC</title>');
                // Link CDN Bootstrap (Hoặc đường dẫn local của bạn)
                win.document.write('<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">');
                win.document.write('</head><body>');
                win.document.write(content);
                win.document.write('</body></html>');
                
                win.document.close();
                win.focus();
                
                // Chờ load CSS xong mới in
                setTimeout(function() {
                    win.print();
                    win.close();
                }, 500);

            } else {
                alert("Lỗi: " + res.message);
            }
        },
        error: function(err) {
            alert("Không thể tải dữ liệu in!");
        }
    });
}

function finishExamination() {
    // 1. Kiểm tra ID
    if (!currentExamId) {
        alert("Chưa chọn bệnh nhân!");
        return;
    }

    // 2. Hỏi xác nhận (Tránh bấm nhầm)
    if (!confirm("Xác nhận kết thúc lượt khám của bệnh nhân này?\nBệnh nhân sẽ được chuyển sang trạng thái 'Đã khám'.")) {
        return;
    }

    // 3. Gọi API
    $.ajax({
        url: '/api/kham-benh/ket-thuc',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ exam_id: currentExamId }),
        success: function(res) {
            if (res.success) {
                alert(res.message);
                
                // Reset ID hiện tại
                currentExamId = null;
                
                // Sử dụng hàm chung để quay về danh sách
                switchTab('danh-sach'); 

                // Tải lại dữ liệu danh sách chờ (để dòng vừa khám biến mất/đổi màu)
                loadWaitingList(1);
                
                // Reset các form nhập liệu cho sạch sẽ
                resetFormKham();
            } else {
                alert(res.message);
            }
        },
        error: function(err) {
            alert("Lỗi hệ thống: Không thể kết thúc khám!");
            console.error(err);
        }
    });
}

// Hàm phụ: Xóa trắng form (Tùy chọn)
function resetFormKham() {
    $('input[type="text"], input[type="number"], textarea').val('');
    $('#kham_ma_bn, #kham_ho_ten').text('---');
    // Xóa bảng thuốc, dịch vụ tạm...
    tempPrescription = [];
    tempServices = [];
    $('#dt_table_body, #cd_table_body').empty();
}

// Hàm gọi số tiếp theo (Gọn gàng với Toast)
function callNextPatient() {
    var roomId = $('#filter_room').val();

    // 1. Validate
    if (!roomId || roomId === 'all') {
        showToast('warning', 'Vui lòng chọn phòng khám cụ thể!');
        return;
    }

    // 2. Gọi API
    // Nút gọi nên disable tạm thời để tránh spam
    var btn = $(event.target).closest('button');
    btn.prop('disabled', true).html('<i class="fa-solid fa-spinner fa-spin"></i> Đang gọi...');

    $.ajax({
        url: '/api/kham-benh/goi-kham',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ 'room_id': roomId }),
        success: function(response) {
            if (response.success) {
                // Gọi thành công -> Toast Xanh
                showToast('success', response.message);
                
                // Load lại danh sách để thấy thay đổi
                loadExamList(); 
            } else {
                // Hết số hoặc lỗi logic -> Toast Vàng/Đỏ
                // Nếu backend trả về 'Hết bệnh nhân chờ', ta dùng warning cho nhẹ nhàng
                var type = response.message.includes('Hết bệnh nhân') ? 'warning' : 'error';
                showToast(type, response.message);
            }
        },
        error: function(err) {
            console.error(err);
            showToast('error', 'Lỗi kết nối máy chủ!');
        },
        complete: function() {
            // Mở lại nút sau khi xong
            btn.prop('disabled', false).html('<i class="fa-solid fa-bullhorn"></i> Gọi');
        }
    });
}
