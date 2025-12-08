/**
 * Hàm hiển thị thông báo Toast
 * @param {string} type - 'success', 'error', 'warning'
 * @param {string} message - Nội dung thông báo
 */
function showToast(type, message) {
    var icon = '';
    var title = '';
    var cssClass = '';

    if (type === 'success') {
        icon = '<i class="fa-solid fa-check-circle"></i>';
        title = 'Thành công!';
        cssClass = 'toast-success';
    } else if (type === 'error') {
        icon = '<i class="fa-solid fa-circle-exclamation"></i>';
        title = 'Thất bại!';
        cssClass = 'toast-error';
    } else if (type === 'warning') {
        icon = '<i class="fa-solid fa-triangle-exclamation"></i>';
        title = 'Cảnh báo!';
        cssClass = 'toast-warning';
    }

    var html = `
        <div class="custom-toast ${cssClass}">
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">
                <h6>${title}</h6>
                <p>${message}</p>
            </div>
        </div>
    `;

    var $toast = $(html);
    
    // Đảm bảo container tồn tại
    if ($('#toast-container').length === 0) {
        $('body').append('<div id="toast-container"></div>');
    }

    $('#toast-container').append($toast);

    // Tự động xóa khỏi DOM sau 4s (thời gian animation kết thúc)
    setTimeout(function() {
        $toast.remove();
    }, 4000);
}