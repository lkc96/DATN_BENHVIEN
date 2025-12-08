// Biến toàn cục để lưu trạng thái
var selectedPatientId = null;   // ID bệnh nhân đang chọn trong bảng
var currentAccountData = null;  // Dữ liệu tài khoản để in phiếu
var currentInvoiceId = null;    
var lastTicketInfo = null;     
var currentPrintData = null; //Dữ liệu phiếu khám

$(document).ready(function() {

    // =========================================================
    // 1. LOGIC XỬ LÝ ĐỊA CHÍNH & TỰ ĐỘNG SINH ĐỊA CHỈ
    // =========================================================
    var localData = [];
    var urlData = 'https://raw.githubusercontent.com/kenzouno1/DiaGioiHanhChinhVN/master/data.json';

    $.getJSON(urlData, function(data) {
        localData = data;
        $("#province").html('<option value="">Chọn Tỉnh/TP</option>');
        $.each(data, function(key, val) {
            $("#province").append('<option value="' + val.Id + '">' + val.Name + '</option>');
        });
    });

    $("#province").change(function() {
        var idTinh = $(this).val();
        $("#district").html('<option value="">Chọn Quận/Huyện</option>');
        $("#ward").html('<option value="">Chọn Phường/Xã</option>');
        
        if (idTinh !== '') {
            var result = localData.find(n => n.Id === idTinh);
            if (result && result.Districts) {
                $.each(result.Districts, function(key, val) {
                    $("#district").append('<option value="' + val.Id + '">' + val.Name + '</option>');
                });
            }
        }
        generateAddress(); 
    });

    $("#district").change(function() {
        var idTinh = $("#province").val();
        var idQuan = $(this).val();
        $("#ward").html('<option value="">Chọn Phường/Xã</option>');

        if (idQuan !== '') {
            var dataProvince = localData.find(n => n.Id === idTinh);
            var dataDistrict = dataProvince.Districts.find(n => n.Id === idQuan);
            if (dataDistrict && dataDistrict.Wards) {
                $.each(dataDistrict.Wards, function(key, val) {
                    $("#ward").append('<option value="' + val.Id + '">' + val.Name + '</option>');
                });
            }
        }
        generateAddress();
    });

    $("#ward, #sonha").on('change input', function() {
        generateAddress();
    });

    function generateAddress() {
        var parts = [];
        var soNha = $("#sonha").val();
        if (soNha) parts.push(soNha);
        var phuong = $("#ward option:selected").text();
        if (phuong && !phuong.includes("Chọn")) parts.push(phuong);
        var quan = $("#district option:selected").text();
        if (quan && !quan.includes("Chọn")) parts.push(quan);
        var tinh = $("#province option:selected").text();
        if (tinh && !tinh.includes("Chọn")) parts.push(tinh);
        $("#diachi_full").val(parts.join(", "));
    }

    // =========================================================
    // 2. LOGIC CHỌN DANH MỤC -> LỌC DỊCH VỤ
    // =========================================================
    $('#catalog_service').change(function() {
        var catalogId = $(this).val();
        $('#service_id').val('');
        $('#service_id option').hide(); 
        
        if(catalogId) {
            $('#service_id option[data-catalog="' + catalogId + '"]').show();
            $('#service_id option:first').show().text('-- Chọn dịch vụ --');
        } else {
            $('#service_id option:first').show().text('-- Vui lòng chọn danh mục trước --');
        }
    });

    // =========================================================
    // 3. LOGIC QUẸT THẺ TỪ (HID/USB)
    // =========================================================
    $('#card_code').focus();

    $('#card_code').on('keypress', function(e) {
        if(e.which == 13) {
            e.preventDefault(); 
            var cardCode = $(this).val();
            if(cardCode) checkPatientByCard(cardCode);
        }
    });

    $('#btnCheckCard').click(function() {
        var cardCode = $('#card_code').val();
        if(cardCode) checkPatientByCard(cardCode);
    });

    function checkPatientByCard(cardCode) {
        $('#card_status').html('<span class="text-warning"><i class="fa-solid fa-spinner fa-spin"></i> Đang đọc...</span>');
        $('#ma_bn').val("BN" + cardCode);

        $.ajax({
            url: '/api/patient-info/' + cardCode,
            type: 'GET',
            success: function(res) {
                if(res.found) {
                    $('#card_status').html('<span class="text-success"><i class="fa-solid fa-check"></i> Đã tìm thấy: ' + res.full_name + '</span>');
                    
                    $('#ho_ten').val(res.full_name);
                    $('#gioi_tinh').val(res.gender);
                    $('#ngay_sinh').val(res.dob);
                    calculateAge();

                    $('#sdt').val(res.phone);
                    $('#cccd').val(res.cccd);
                    $('#diachi_full').val(res.address);
                    
                    if(res.card_data) {
                        var formattedBalance = new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(res.card_data.balance);
                        $('#so_du_the').val(formattedBalance);
                    }
                    $('#catalog_service').focus();
                } else {
                    $('#card_status').html('<span class="text-primary"><i class="fa-solid fa-user-plus"></i> Thẻ mới - Mời nhập thông tin</span>');
                    $('#ho_ten').val('').focus(); 
                    $('#sdt').val('');
                    $('#cccd').val('');
                    $('#diachi_full').val('');
                    $('#sonha').val('');
                    $('#tuoi_bn').val('');
                    $('#so_du_the').val('0 đ');
                }
            },
            error: function() {
                $('#card_status').text('Lỗi kết nối server!');
            }
        });
    }

    function calculateAge() {
        var dobStr = $('#ngay_sinh').val();
        if (!dobStr || dobStr.length < 10) {
            $('#tuoi_bn').val('');
            return;
        }
        var parts = dobStr.split('/');
        if (parts.length === 3) {
            var day = parseInt(parts[0], 10);
            var month = parseInt(parts[1], 10);
            var year = parseInt(parts[2], 10);
            var today = new Date();
            var age = today.getFullYear() - year;
            if (today.getMonth() + 1 < month || (today.getMonth() + 1 == month && today.getDate() < day)) {
                age--;
            }
            $('#tuoi_bn').val(age);
        }
    }
    $('#ngay_sinh').on('blur change input', calculateAge);

    // =========================================================
    // 4. LOGIC NÚT LƯU (SUBMIT)
    // =========================================================
    $('.btn-save').click(function(e) {
        e.preventDefault();

        var formData = {
            'ma_the': $('#card_code').val(),
            'ho_ten': $('#ho_ten').val(),
            'gioi_tinh': $('#gioi_tinh').val(),
            'ngay_sinh': $('#ngay_sinh').val(),
            'sdt': $('#sdt').val(),
            'cccd': $('#cccd').val(),
            'dia_chi': $('#diachi_full').val(),
            'dich_vu_id': $('#service_id').val(),
            'phong_kham_id': $('#room_id').val(),
            'ly_do_kham': $('#ly_do_kham').val(),
            'nap_tien': $('#nap_tien').val() || 0
        };

        if (!formData.ma_the) { alert("Vui lòng quẹt thẻ trước!"); $('#card_code').focus(); return; }
        if (!formData.ho_ten) { alert("Vui lòng nhập họ tên!"); $('#ho_ten').focus(); return; }
        if (!formData.dich_vu_id) { alert("Vui lòng chọn dịch vụ khám!"); $('#catalog_service').focus(); return; }

        $.ajax({
            url: '/api/tiep-don/luu',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                if (response.success) {
                    var displayId = "BN" + formData.ma_the;
                    lastTicketInfo = {
                        ma_bn: displayId,
                        ho_ten: response.patient_name,
                        nam_sinh: $('#ngay_sinh').val(),
                        gioi_tinh: $('#gioi_tinh option:selected').text(),
                        
                        // Lấy text của phòng khám đang chọn
                        phong_kham: $("#room_id option:selected").text(),
                        // Lấy text của dịch vụ đang chọn
                        dich_vu: $("#service_id option:selected").text(),
                        
                        // Lấy STT từ server trả về
                        stt: response.stt 
                    };
                    alert("ĐĂNG KÝ THÀNH CÔNG!\n-------------------------\nMã BN: BN" + formData.ma_the + "\nBệnh nhân: " + response.patient_name + "\nSố thứ tự: " + response.stt);
                    location.reload(); 
                }
            },
            error: function(err) {
                alert("Lỗi: " + (err.responseJSON ? err.responseJSON.message : "Không xác định"));
            }
        });
    });

    // =========================================================
    // 5. LOGIC TAB & DANH SÁCH & TÀI KHOẢN
    // =========================================================
    
    // Khởi tạo Lịch
    flatpickr("#filter_date", {
        dateFormat: "d/m/Y",
        defaultDate: "today",
        locale: "vn",
        allowInput: true,
        onReady: function(selectedDates, dateStr, instance) {
            var $inputGroup = $(instance.element).closest('.input-group');
            var $icon = $inputGroup.find('.input-group-text');
            $icon.click(function() { instance.open(); });
        }
    });

    // Hàm chuyển Tab
   window.switchTab = function(tabName) {
        // BƯỚC 1: Ẩn TOÀN BỘ 4 view (Thêm #view-thu-tien vào đây)
        $('#view-dang-ky, #view-danh-sach, #view-tai-khoan, #view-thu-tien').hide();
        
        // BƯỚC 2: Xóa class active ở menu
        $('.nav-link').removeClass('active');

        // BƯỚC 3: Hiện view tương ứng
        if (tabName === 'dang-ky') {
            $('#view-dang-ky').show();
            $('#tab-dang-ky').addClass('active');
        } 
        else if (tabName === 'danh-sach') {
            $('#view-danh-sach').show();
            $('#tab-danh-sach').addClass('active');
            loadReceptionList(); // Tải lại danh sách
        }
        else if (tabName === 'tai-khoan') {
            $('#view-tai-khoan').show();
            $('#tab-tai-khoan').addClass('active');
            loadAccountInfo(); // Tải thông tin tài khoản
        }
        else if (tabName === 'thu-tien') {
            $('#view-thu-tien').show();
            $('#tab-thu-tien').addClass('active');
            loadInvoiceInfo(); // Gọi hàm tải hóa đơn
        }
    };

    $('.btn-primary:contains("TÌM KIẾM")').click(function() {
        loadReceptionList(1); 
    });

    // Hàm tải danh sách
    function loadReceptionList(page = 1) {
        var tbody = $('#table_body_ds');
        tbody.html('<tr><td colspan="10" class="text-center py-4 text-muted"><i class="fa-solid fa-spinner fa-spin me-2"></i> Đang tải dữ liệu...</td></tr>');
        
        var keyword = $('#filter_keyword').val();
        var dateRange = $('#filter_date').val();

        $.ajax({
            url: '/api/tiep-don/danh-sach',
            type: 'GET',
            data: { keyword: keyword, date: dateRange, page: page },
            success: function(response) {
                if (response.success) {
                    tbody.empty(); 
                    if (response.data.length === 0) {
                        tbody.html('<tr><td colspan="10" class="text-center py-3">Không tìm thấy dữ liệu</td></tr>');
                        $('#pagination_info').text('0 bản ghi');
                        $('#pagination_links').empty();
                        return;
                    }

                    $.each(response.data, function(index, item) {
                        // [QUAN TRỌNG] Thêm data-id và class con trỏ để click chọn dòng
                        var row = `
                            <tr class="align-middle" data-id="${item.patient_id}" style="cursor: pointer;">
                                <td class="text-center" style="font-weight: 500;">${item.stt}</td>
                                <td class="fw-bold text-dark">${item.ma_bn}</td>
                                <td class="text-uppercase fw-bold text-primary">${item.ho_ten}</td>
                                <td class="text-muted small">${item.ma_dk_kham}</td>
                                <td>${item.thoi_gian}</td>
                                <td class="text-center">${item.gioi_tinh || ''}</td>
                                <td class="text-center">${item.ngay_sinh}</td>
                                <td class="text-center">${item.sdt}</td>
                                <td class="text-center small">${item.trang_thai}</td>
                                <td class="text-center">
                                    <button class="btn btn-sm btn-link text-primary p-0 mx-1" title="Sửa"><i class="fa-solid fa-pen"></i></button>
                                    <button class="btn btn-sm btn-link text-danger p-0 mx-1" title="Xóa" onclick="event.stopPropagation(); deleteSession(${item.id})">
                                        <i class="fa-solid fa-trash"></i>
                                    </button>
                                </td>
                            </tr>
                        `;
                        tbody.append(row);
                    });

                    renderPagination(response.pagination);
                }
            },
            error: function() { tbody.html('<tr><td colspan="10" class="text-center text-danger">Lỗi kết nối Server</td></tr>'); }
        });
    }

    // Sự kiện Click vào hàng để chọn (Highlight)
    $('#table_body_ds').on('click', 'tr', function() {
        $('#table_body_ds tr').removeClass('table-primary'); // Xóa highlight cũ
        $(this).addClass('table-primary'); // Highlight dòng mới
        selectedPatientId = $(this).data('id'); // Lưu ID
    });

// =========================================================
// 10. LOGIC NẠP TIỀN (ĐÃ SỬA ĐỂ CẬP NHẬT NGAY LẬP TỨC)
// =========================================================
window.openDepositModal = function() {
    if (!selectedPatientId) {
        alert("Chưa chọn bệnh nhân!");
        return;
    }

    var amountStr = prompt("Nhập số tiền muốn nạp (VNĐ):", "50000");
    
    if (amountStr != null) {
        var amount = parseFloat(amountStr);
        if (isNaN(amount) || amount <= 0) {
            alert("Vui lòng nhập số tiền hợp lệ!");
            return;
        }

        $.ajax({
            url: '/api/tiep-don/nap-tien',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                patient_id: selectedPatientId,
                amount: amount
            }),
            success: function(response) {
                if (response.success) {
                    alert("NẠP TIỀN THÀNH CÔNG!\nSố dư mới: " + response.new_balance_formatted + " VNĐ");

                    $('#detail_balance').val(response.new_balance_formatted);

                    if($('#so_du_the').length) {
                        $('#so_du_the').val(response.new_balance_formatted + " VNĐ");
                    }

                    if (currentAccountData) {
                        currentAccountData.balance = response.new_balance;
                    }

                } else {
                    alert("Lỗi: " + response.message);
                }
            },
            error: function(err) {
                alert("Lỗi kết nối Server");
            }
        });
    }
};

    // Hàm load thông tin tài khoản (Tab 3)
    function loadAccountInfo() {
        if (!selectedPatientId) {
            $('#account-alert').show();
            $('#account-info-content').hide();
            return;
        }
        $('#account-alert').hide();
        
        $.ajax({
            url: '/api/tiep-don/tai-khoan/' + selectedPatientId,
            type: 'GET',
            success: function(response) {
                if (response.success) {
                    var data = response.data;
                    currentAccountData = data;
                    // Đổ dữ liệu vào FORM
                // 1. Hành chính
                $('#detail_ma_bn').val(data.ma_bn);
                $('#detail_ho_ten').val(data.ho_ten);
                $('#detail_gioi_tinh').val(data.gioi_tinh);
                $('#detail_ngay_sinh').val(data.ngay_sinh);
                $('#detail_sdt').val(data.sdt);
                $('#detail_cccd').val(data.cccd);
                $('#detail_dia_chi').val(data.dia_chi);
                $('#detail_nguoi_nha').val(data.nguoi_nha);

                // 2. Tài khoản & Thẻ
                $('#detail_ma_the').val(data.ma_the);
                $('#detail_ngay_tao_the').val(data.card_created);
                $('#detail_trang_thai_the').val(data.card_status);
                $('#detail_username').val(data.username);
                $('#detail_email').val(data.password_hash);

                // Format tiền
                var formattedBal = new Intl.NumberFormat('vi-VN').format(data.balance);
                $('#detail_balance').val(formattedBal);

                // Reset trạng thái nút
                cancelEditMode(); 
                $('#account-info-content').fadeIn();
                    // $('#acc_ma_bn').text(data.ma_bn);
                    // $('#acc_ma_the').text(data.ma_the);
                    // $('#acc_ho_ten').text(data.ho_ten);
                    // $('#acc_email').text(data.email);
                    // $('#acc_username').text(data.username);
                    // $('#acc_password_hash').text(data.password_hash);
                    // var formattedBal = new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(data.balance);
                    // $('#acc_balance').text(formattedBal);
                    // $('#account-info-content').fadeIn();
                }
            },
            error: function() { alert("Lỗi tải thông tin tài khoản"); }
        });
    }

    // Hàm in phiếu tài khoản
    window.printAccountTicket = function() {
        if (!currentAccountData) return;

        // Điền dữ liệu vào khung in
        $('#p_ho_ten').text(currentAccountData.ho_ten);
        $('#p_ma_bn').text(currentAccountData.ma_bn);
        $('#p_username').text(currentAccountData.username);
        $('#p_password').text(currentAccountData.password_print);

        // Mở cửa sổ in
        var printContent = document.getElementById('print-area').innerHTML;
        var win = window.open('', '', 'height=600,width=400');
        win.document.write('<html><head><title>In Phiếu Tài Khoản</title>');
        win.document.write('<style>body{font-family: Arial, sans-serif;}</style>'); // Thêm style cơ bản cho đẹp
        win.document.write('</head><body>');
        win.document.write(printContent);
        win.document.write('</body></html>');
        win.document.close();
        win.focus();
        setTimeout(function(){ win.print(); win.close(); }, 500); // Đợi load xong mới in
    };

    // Hàm vẽ phân trang
    function renderPagination(pageData) {
        var start = (pageData.current_page - 1) * pageData.per_page + 1;
        var end = start + pageData.per_page - 1;
        if (end > pageData.total_items) end = pageData.total_items;
        
        $('#pagination_info').html(`<i class="fa-regular fa-file-excel text-success me-1"></i> ${start} đến ${end} / ${pageData.total_items} bản ghi`);

        var html = '';
        var current = pageData.current_page;
        var total = pageData.total_pages;

        if (current > 1) {
            html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="loadReceptionList(${current - 1})">«</a></li>`;
        } else {
            html += `<li class="page-item disabled"><a class="page-link" href="#">«</a></li>`;
        }

        var startPage = Math.max(1, current - 2);
        var endPage = Math.min(total, current + 2);

        for (var i = startPage; i <= endPage; i++) {
            if (i === current) {
                html += `<li class="page-item active"><a class="page-link" href="#">${i}</a></li>`;
            } else {
                html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="loadReceptionList(${i})">${i}</a></li>`;
            }
        }

        if (current < total) {
            html += `<li class="page-item"><a class="page-link" href="javascript:void(0)" onclick="loadReceptionList(${current + 1})">»</a></li>`;
        } else {
            html += `<li class="page-item disabled"><a class="page-link" href="#">»</a></li>`;
        }

        $('#pagination_links').html(html);
    }

    window.loadReceptionList = loadReceptionList;

    // Logic Xóa phiếu khám
    window.deleteSession = function(id) {
        if (!confirm('Bạn có chắc chắn muốn xóa phiếu khám này không?')) return;

        $.ajax({
            url: '/api/tiep-don/xoa',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ id: id }),
            success: function(response) {
                if (response.success) {
                    alert(response.message);
                    loadReceptionList(); 
                } else {
                    alert(response.message);
                }
            },
            error: function(err) {
                var msg = err.responseJSON ? err.responseJSON.message : "Lỗi kết nối";
                alert(msg);
            }
        });
    };

    // Bật chế độ sửa
window.enableEditMode = function() {
    // Bỏ readonly cho các trường được phép sửa
    $('#detail_ho_ten, #detail_ngay_sinh, #detail_sdt, #detail_cccd, #detail_dia_chi, #detail_nguoi_nha, #detail_email').prop('readonly', false);
    $('#detail_gioi_tinh, #detail_trang_thai_the').prop('disabled', false); // Select box dùng disabled

    // Đổi nút
    $('#btn-edit').hide();
    $('#btn-save-info').show();
    $('#btn-cancel-info').show();
};

// Hủy sửa (Revert lại dữ liệu cũ)
window.cancelEditMode = function() {
    // Khóa lại
    $('#detail_ho_ten, #detail_ngay_sinh, #detail_sdt, #detail_cccd, #detail_dia_chi, #detail_nguoi_nha, #detail_email').prop('readonly', true);
    $('#detail_gioi_tinh, #detail_trang_thai_the').prop('disabled', true);

    // Đổi nút
    $('#btn-edit').show();
    $('#btn-save-info').hide();
    $('#btn-cancel-info').hide();
    
    // Nếu đang sửa dở mà hủy thì load lại dữ liệu gốc
    if (currentAccountData) {
        $('#detail_ho_ten').val(currentAccountData.ho_ten);
        // ... (có thể load lại các field khác nếu cần thiết)
    }
};

// Lưu thông tin sửa
window.savePatientInfo = function() {
    var updateData = {
        patient_id: selectedPatientId,
        ho_ten: $('#detail_ho_ten').val(),
        gioi_tinh: $('#detail_gioi_tinh').val(),
        ngay_sinh: $('#detail_ngay_sinh').val(),
        sdt: $('#detail_sdt').val(),
        cccd: $('#detail_cccd').val(),
        dia_chi: $('#detail_dia_chi').val(),
        nguoi_nha: $('#detail_nguoi_nha').val(),
        email: $('#detail_email').val(),
        card_status: $('#detail_trang_thai_the').val()
    };

    $.ajax({
        url: '/api/tiep-don/cap-nhat-benh-nhan',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(updateData),
        success: function(response) {
            if (response.success) {
                alert(response.message);
                cancelEditMode();
                loadAccountInfo(); // Load lại để cập nhật cache
            } else {
                alert("Lỗi: " + response.message);
            }
        }
    });
};

// Xóa hồ sơ bệnh nhân (Full)
window.deletePatientFull = function() {
    if (!confirm("CẢNH BÁO NGUY HIỂM!\n\nHành động này sẽ xóa vĩnh viễn Hồ sơ bệnh nhân, Tài khoản và Thẻ từ.\nBạn chỉ nên xóa nếu đây là dữ liệu nhập sai.\n\nBạn có chắc chắn muốn xóa?")) {
        return;
    }

    $.ajax({
        url: '/api/tiep-don/xoa-benh-nhan',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ patient_id: selectedPatientId }),
        success: function(response) {
            if (response.success) {
                alert(response.message);
                // Quay về danh sách và load lại
                switchTab('danh-sach');
                loadReceptionList();
            } else {
                alert("Không thể xóa: " + response.message);
            }
        }
    });
};

// =========================================================
// 11. LOGIC TAB THU TIỀN (CẬP NHẬT)
// =========================================================

function loadInvoiceInfo() {
    if (!selectedPatientId) {
        alert("Vui lòng chọn một bệnh nhân trước!");
        switchTab('danh-sach');
        return;
    }

    // Reset giao diện
    $('#bill_table_body').html('');
    $('#pay_total').val('0');
    $('#bill_qr_code').hide();
    $('#bill_qr_icon').show();
    currentInvoiceId = null;

    // [MỚI] Lấy ngày giờ hiện tại hiển thị luôn
    var now = new Date();
    var dateStr = now.getDate() + '/' + (now.getMonth()+1) + '/' + now.getFullYear() + ' ' + now.getHours() + ':' + now.getMinutes();
    $('#pay_date').val(dateStr);

    $.ajax({
        url: '/api/tiep-don/hoa-don/' + selectedPatientId,
        type: 'GET',
        success: function(response) {
            if (response.success) {
                var data = response.data;
                currentInvoiceId = data.invoice_id;

                currentPrintData = {
                    ma_bn: data.ma_bn,
                    ho_ten: data.ho_ten,
                    nam_sinh: data.ngay_sinh, // Dùng ngày sinh hoặc năm sinh tùy ý
                    gioi_tinh: data.gioi_tinh,
                    phong_kham: data.phong_kham_ten, // Tên phòng lấy từ API sửa ở bước 1
                    stt: data.stt,                   // Số thứ tự lấy từ API sửa ở bước 1
                    dich_vu: data.details.length > 0 ? data.details[0].service_name : "Khám bệnh"
                };
                // 1. Điền Header & Thông tin mới
                $('#bill_ma_bn').text(data.ma_bn);
                $('#bill_ho_ten').text(data.ho_ten);
                $('#bill_ngay_sinh').text(data.ngay_sinh);
                $('#bill_gioi_tinh').text(data.gioi_tinh);
                $('#bill_tuoi').text(data.tuoi);
                
                // [MỚI] Điền Phòng, Bác sĩ, Trạng thái
                $('#bill_phong_kham').text(data.phong_kham);
                $('#bill_bac_si').text(data.bac_si);
                $('#bill_trang_thai').text(data.trang_thai);

                // [MỚI] Hiển thị QR Code
                if(data.qr_url) {
                    $('#bill_qr_code').attr('src', data.qr_url).show();
                    $('#bill_qr_icon').hide();
                }

                // 2. Điền Bảng dịch vụ (Có checkbox click được)
                var total = 0;
                $.each(data.details, function(i, item) {
                    var priceFmt = new Intl.NumberFormat('vi-VN').format(item.unit_price);
                    var totalFmt = new Intl.NumberFormat('vi-VN').format(item.total);
                    
                    var row = `
                        <tr>
                            <td class="text-center">
                                <input type="checkbox" class="chk-service" value="${item.total}" checked onchange="recalcTotal()">
                            </td>
                            <td>${item.service_name}</td>
                            <td class="text-center">Lần</td>
                            <td class="text-center">${item.quantity}</td>
                            <td class="text-end">${priceFmt}</td>
                            <td class="text-end fw-bold">${totalFmt}</td>
                        </tr>
                    `;
                    $('#bill_table_body').append(row);
                    total += item.total;
                });

                // Cập nhật tổng tiền ban đầu
                updateTotalDisplay(total);

            } else {
                alert(response.message);
                $('#bill_ho_ten').text("KHÔNG CÓ HÓA ĐƠN");
            }
        },
        error: function() { alert("Lỗi tải thông tin hóa đơn"); }
    });
}

// [MỚI] Hàm tính lại tổng tiền khi click checkbox
window.recalcTotal = function() {
    var total = 0;
    $('.chk-service:checked').each(function() {
        total += parseFloat($(this).val());
    });
    updateTotalDisplay(total);
};

// [MỚI] Hàm chọn tất cả
window.toggleAllServices = function(source) {
    $('.chk-service').prop('checked', source.checked);
    recalcTotal();
};

// Hàm hiển thị số tiền
function updateTotalDisplay(amount) {
    var fmt = new Intl.NumberFormat('vi-VN').format(amount);
    $('#bill_table_total').text(fmt);
    $('#pay_total').val(fmt);
    // Nếu có ô thực thu thì update luôn
    if($('#pay_actual').length) $('#pay_actual').val(fmt);
}
// Hàm Xử lý thanh toán
window.submitPayment = function() {
    if (!currentInvoiceId) {
        alert("Không có hóa đơn nào để thanh toán!");
        return;
    }

    if(!confirm("Xác nhận thanh toán hóa đơn này?")) return;

    var method = $('#pay_method').val(); // cash hoặc card

    $.ajax({
        url: '/api/tiep-don/thanh-toan',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            invoice_id: currentInvoiceId,
            payment_method: method
        }),
        success: function(response) {
            if (response.success) {
                alert("THANH TOÁN THÀNH CÔNG!\nBệnh nhân có thể vào khám.");
                
                // 2. Xóa dữ liệu hóa đơn trên màn hình (Ẩn hóa đơn đi)
                $('#bill_table_body').html('<tr><td colspan="7" class="text-center text-muted fst-italic py-5">Không có dịch vụ cần thanh toán</td></tr>');
                
                // Reset các ô tiền về 0
                $('#pay_total').val('0');
                if($('#pay_actual').length) $('#pay_actual').val('0');
                $('#bill_table_total').text('0');
                
                // Ẩn QR Code cũ
                $('#bill_qr_code').hide();
                $('#bill_qr_icon').show();

                // 3. Cập nhật trạng thái trên thanh Header thành Đã thanh toán (Màu xanh)
                $('#bill_trang_thai')
                    .removeClass('bg-warning text-dark')
                    .addClass('bg-success text-white')
                    .text('Đã thanh toán');

                // 4. Reset biến ID để ngăn bấm nút Lưu lần nữa
                currentInvoiceId = null;
            } else {
                alert("Lỗi thanh toán: " + response.message);
            }
        },
        error: function() { alert("Lỗi kết nối Server"); }
    });
};
    // =========================================================
    // HÀM IN PHIẾU TỪ TRANG THU TIỀN (ĐÃ ĐƯA VÀO TRONG READY)
    // =========================================================
    function printExaminationTicketFromBill() {
        // Kiểm tra biến toàn cục currentPrintData (được gán lúc load hóa đơn)
        if (!currentPrintData) {
            alert("Chưa có dữ liệu phiếu khám để in! Vui lòng chọn bệnh nhân và tải hóa đơn trước.");
            return;
        }

        // 1. Điền dữ liệu vào mẫu in ẩn
        $('#p_ticket_mabn').text(currentPrintData.ma_bn);
        $('#p_ticket_hoten').text(currentPrintData.ho_ten);
        $('#p_ticket_namsinh').text(currentPrintData.nam_sinh);
        $('#p_ticket_gioitinh').text(currentPrintData.gioi_tinh);
        
        // Điền Phòng khám & Số thứ tự
        $('#p_ticket_phong').text(currentPrintData.phong_kham || "Chưa phân phòng");
        
        // Format số thứ tự (01, 02...)
        var sttVal = currentPrintData.stt;
        var sttFormatted = sttVal < 10 ? '0' + sttVal : sttVal;
        $('#p_ticket_stt').text(sttFormatted);

        $('#p_ticket_dichvu').text(currentPrintData.dich_vu);

        // Ngày giờ in phiếu
        var now = new Date();
        var timeStr = now.getDate() + '/' + (now.getMonth()+1) + '/' + now.getFullYear() + ' ' + now.getHours() + ':' + now.getMinutes();
        $('#p_ticket_ngay').text(timeStr);

        // 2. Mở cửa sổ in
        var printContent = document.getElementById('print-ticket-area').innerHTML;
        var win = window.open('', '', 'height=600,width=400');
        
        win.document.write('<html><head><title>In Phiếu Khám</title>');
        win.document.write('<style>');
        win.document.write('body { font-family: monospace; display: flex; justify-content: center; margin-top: 20px;}');
        win.document.write('.ticket-container { width: 300px; border: 1px solid #000; padding: 15px; }'); 
        win.document.write('</style>');
        win.document.write('</head><body>');
        win.document.write(printContent);
        win.document.write('</body></html>');
        
        win.document.close();
        win.focus();
        
        setTimeout(function() { 
            win.print(); 
            win.close(); 
        }, 500);
    }

    // [CỰC KỲ QUAN TRỌNG] 
    // Dòng này giúp HTML bên ngoài (onclick) gọi được hàm bên trong jQuery
    window.printExaminationTicketFromBill = printExaminationTicketFromBill;
});