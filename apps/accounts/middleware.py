from django.conf import settings
from django.shortcuts import redirect

# 這些路徑即使 must_change_password 為 True 也要放行，
# 否則使用者會被導向設定密碼頁後又被導回來，形成無限迴圈。
_EXEMPT_PATHS = (
    '/accounts/password/change/',
    '/accounts/logout/',
)

# 本機開發用 runserver 直接送靜態檔/媒體檔時，這些請求也會走過這個 middleware，
# 若不放行，設定密碼頁上的圖片會被攔成 302 導致顯示不出來（正式環境由 Nginx 直接處理，不受影響）。
_EXEMPT_PREFIXES = ('/admin/', settings.STATIC_URL, settings.MEDIA_URL)


class ForcePasswordChangeMiddleware:
    """
    幹部手動建立團員帳號或核准校友報到時，會給一組系統產生的臨時密碼，
    並將 User.must_change_password 設為 True。
    這個 middleware 攔截該使用者的所有請求，強制導向設定新密碼頁面，
    直到完成設定為止，避免臨時密碼被長期當作正式密碼使用。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (
            user is not None and user.is_authenticated
            and getattr(user, 'must_change_password', False)
            and not request.path.startswith(_EXEMPT_PREFIXES)
            and request.path not in _EXEMPT_PATHS
        ):
            return redirect('accounts:change_password')
        return self.get_response(request)
