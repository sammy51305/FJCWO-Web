"""
登入失敗次數限制：同一帳號連續登入失敗 MAX_FAILURES 次，鎖住 LOCKOUT_SECONDS 秒。

為什麼以「帳號」計、不以 IP 計：
    正式站經 Tailscale Funnel 轉進來，waitress 看到的 REMOTE_ADDR 一律是 127.0.0.1，
    以 IP 計會讓一個人猜錯就鎖住全團。代價是別人可以故意打錯某人的帳號讓他暫時登不進來，
    所以鎖定時間刻意短（15 分鐘），而且 Google 登入不受影響，被惡意鎖住時仍有路可走。

三個接點，網站登入頁與 /admin/ 登入都涵蓋：
    - ThrottledModelBackend：認證前先看是否鎖住，鎖住就整個拒絕（/admin/ 也走這裡）
    - user_login_failed 訊號：記一次失敗
    - user_logged_in 訊號：登入成功就歸零
    登入頁表單另外在 clean() 先檢查，才能顯示「請稍後再試」而不是「帳號或密碼錯誤」。

計數存在 Django cache（未設定 CACHES，預設為單一行程的記憶體快取）。正式站是單一 waitress
行程，計數在所有執行緒間共用；重啟網站會歸零，可以接受。
"""
import hashlib

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.dispatch import receiver

MAX_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60
LOCKOUT_MESSAGE = f'登入失敗次數過多，此帳號暫時鎖定，請 {LOCKOUT_SECONDS // 60} 分鐘後再試。'


def _key(username):
    # 帳號正規化後再雜湊：大小寫、前後空白不同仍算同一個帳號；cache key 也不會出現原始帳號
    normalized = (username or '').strip().lower()
    return 'login-fail:' + hashlib.sha256(normalized.encode()).hexdigest()


def failure_count(username):
    return cache.get(_key(username), 0)


def is_locked(username):
    return bool(username) and failure_count(username) >= MAX_FAILURES


def record_failure(username):
    """記一次失敗。每次失敗都把期限往後推，所以是「最後一次失敗後 15 分鐘」才解鎖。"""
    if not username:
        return
    key = _key(username)
    cache.set(key, cache.get(key, 0) + 1, LOCKOUT_SECONDS)


def reset(username):
    cache.delete(_key(username))


class ThrottledModelBackend(ModelBackend):
    """與 ModelBackend 相同，但帳號鎖定期間一律拒絕（密碼對也不行）。"""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if is_locked(username):
            # PermissionDenied 讓 django.contrib.auth.authenticate 直接停止、不再試其他 backend
            raise PermissionDenied(LOCKOUT_MESSAGE)
        return super().authenticate(request, username=username, password=password, **kwargs)


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request=None, **kwargs):
    record_failure(credentials.get(get_user_model().USERNAME_FIELD))


@receiver(user_logged_in)
def _on_logged_in(sender, request, user, **kwargs):
    reset(user.get_username())
