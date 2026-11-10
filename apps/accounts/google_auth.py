"""
Google 帳號登入（OpenID Connect，authorization code flow + PKCE）。

設計重點（見 DESIGN 4.1 Google 登入）：
- **只登入、不註冊**：Google 帳號必須對應到「已存在且啟用」的 User，比對不到就拒絕。
  帳號一律由幹部建立或入團申請核准產生，這條規則不因 Google 登入而改變。
- 第一次登入以 Google 回傳的「已驗證 email」比對 User.email（不分大小寫），
  比對成功就把 Google 的 `sub` 寫進 User.google_sub；之後只認 sub。
- 不引入第三方套件：整個流程只有「導去 Google」與「用 code 換 token」兩步。
  id_token 是我們自己透過 TLS 直接向 Google token endpoint 取得的，依 OIDC Core 3.1.3.7
  可以不驗簽章，只驗 iss / aud / exp / nonce。
- 沒設 GOOGLE_OAUTH_CLIENT_ID / SECRET 時整個功能關閉：按鈕不顯示、兩個網址回 404。
"""
import base64
import hashlib
import json
import logging
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import User

logger = logging.getLogger(__name__)

AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
VALID_ISSUERS = ('https://accounts.google.com', 'accounts.google.com')
SESSION_KEY = 'google_oauth'


class GoogleAuthError(Exception):
    """與 Google 交換 token 或驗證 id_token 失敗。訊息只寫 log，不顯示給使用者。"""


def google_login_enabled():
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def _redirect_uri(request):
    # 正式站在 Tailscale Funnel 後面，靠 SECURE_PROXY_SSL_HEADER 才會組出 https 網址；
    # 這個值必須與 Google Cloud Console 登記的「已授權的重新導向 URI」逐字相同。
    return request.build_absolute_uri(reverse('accounts:google_callback'))


def _safe_next(request, next_url):
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return settings.LOGIN_REDIRECT_URL


def google_login(request):
    """登入：未登入者導去 Google 授權頁。"""
    if not google_login_enabled():
        raise Http404
    if request.user.is_authenticated:
        return redirect('/')
    return _authorize_redirect(request, next_url=request.GET.get('next', ''))


@login_required
@require_POST
def google_link(request):
    """
    綁定：已登入的團員主動綁一個 Google 帳號，不要求 Gmail 與系統 email 相同。
    給「系統 email 填的是學校信箱、Google 用的是私人 Gmail」這類比對不到的情況用。
    """
    if not google_login_enabled():
        raise Http404
    return _authorize_redirect(request, next_url=reverse('accounts:profile'),
                               link_user_id=request.user.pk)


@login_required
@require_POST
def google_unlink(request):
    if not google_login_enabled():
        raise Http404
    request.user.google_sub = None
    request.user.save(update_fields=['google_sub'])
    messages.success(request, '已解除 Google 帳號綁定。')
    return redirect('accounts:profile')


def _authorize_redirect(request, next_url, link_user_id=None):
    """產生 state / nonce / PKCE 存進 session，導去 Google 授權頁。"""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode('ascii')).digest()
    ).rstrip(b'=').decode('ascii')

    request.session[SESSION_KEY] = {
        'state': state,
        'nonce': nonce,
        'verifier': verifier,
        'next': next_url,
        'link_user_id': link_user_id,
    }
    params = {
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri': _redirect_uri(request),
        'response_type': 'code',
        'scope': 'openid email',
        'state': state,
        'nonce': nonce,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        # 讓使用者每次都能選帳號，避免瀏覽器裡登著別的 Google 帳號就直接被帶過去
        'prompt': 'select_account',
    }
    return redirect(f'{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}')


def _exchange_code(code, redirect_uri, verifier):
    """用 authorization code 向 Google 換 token，回傳 id_token 的 claims（尚未驗 nonce）。"""
    data = urllib.parse.urlencode({
        'code': code,
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
        'code_verifier': verifier,
    }).encode('ascii')
    req = urllib.request.Request(TOKEN_ENDPOINT, data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')[:500]
        raise GoogleAuthError(f'token endpoint HTTP {e.code}: {body}') from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise GoogleAuthError(f'token endpoint 連線或解析失敗: {e}') from e

    id_token = payload.get('id_token')
    if not id_token:
        raise GoogleAuthError('token 回應沒有 id_token')
    return _decode_id_token(id_token)


def _decode_id_token(id_token):
    try:
        segment = id_token.split('.')[1]
        segment += '=' * (-len(segment) % 4)
        claims = json.loads(base64.urlsafe_b64decode(segment))
    except (IndexError, ValueError) as e:
        raise GoogleAuthError(f'id_token 格式錯誤: {e}') from e

    if claims.get('iss') not in VALID_ISSUERS:
        raise GoogleAuthError(f'iss 不符: {claims.get("iss")}')
    if claims.get('aud') != settings.GOOGLE_OAUTH_CLIENT_ID:
        raise GoogleAuthError('aud 不符')
    if not isinstance(claims.get('exp'), (int, float)) or claims['exp'] < time.time():
        raise GoogleAuthError('id_token 已過期')
    if not claims.get('sub'):
        raise GoogleAuthError('id_token 沒有 sub')
    return claims


def _deny_guest(user):
    # 與 BootstrapAuthenticationForm.confirm_login_allowed 同一條規則：槍手一律不可登入
    if user.role == User.Role.GUEST:
        return None, '此帳號無法登入系統。'
    return user, None


def _resolve_user(claims):
    """
    依 claims 找出要登入的 User；找不到回傳 (None, 給使用者看的錯誤訊息)。
    先認 sub（已綁定），再以已驗證 email 比對並綁定。
    """
    sub = claims['sub']
    user = User.objects.filter(google_sub=sub).first()
    if user:
        return _deny_guest(user)

    email = (claims.get('email') or '').strip()
    if not email or claims.get('email_verified') is not True:
        return None, '這個 Google 帳號的 email 尚未經 Google 驗證，無法登入。'

    matches = list(User.objects.filter(email__iexact=email)[:2])
    if len(matches) != 1:
        return None, (
            f'系統中沒有 email 為 {email} 的團員資料。'
            '請改用帳號密碼登入，或請幹部確認你的 email 是否填寫正確。'
        )
    user = matches[0]
    if user.role == User.Role.GUEST:
        return _deny_guest(user)
    if user.google_sub and user.google_sub != sub:
        # 這筆團員資料已綁了另一個 Google 帳號：不自動改綁，避免 email 被挪用時帳號被接管
        return None, '這筆團員資料已綁定其他 Google 帳號，請聯絡幹部處理。'

    user.google_sub = sub
    user.save(update_fields=['google_sub'])
    logger.info('Google 登入首次綁定：user=%s', user.pk)
    return user, None


def google_callback(request):
    if not google_login_enabled():
        raise Http404

    stored = request.session.pop(SESSION_KEY, None)
    # 綁定流程（已登入）失敗時回個人資料頁；登入流程回登入頁
    linking = bool(stored and stored.get('link_user_id'))
    login_url = reverse('accounts:profile' if linking else 'accounts:login')

    if request.GET.get('error'):
        # 使用者在 Google 頁面按了取消（access_denied）等
        messages.info(request, '已取消 Google 登入。')
        return redirect(login_url)

    state = request.GET.get('state', '')
    code = request.GET.get('code', '')
    if not stored or not code or not constant_time_compare(state, stored['state']):
        messages.error(request, 'Google 登入驗證失敗（可能逾時或重複送出），請重新操作。')
        return redirect(login_url)

    try:
        claims = _exchange_code(code, _redirect_uri(request), stored['verifier'])
        if not constant_time_compare(claims.get('nonce', ''), stored['nonce']):
            raise GoogleAuthError('nonce 不符')
    except GoogleAuthError as e:
        logger.warning('Google 登入失敗：%s', e)
        messages.error(request, '無法完成 Google 登入，請稍後再試或改用帳號密碼登入。')
        return redirect(login_url)

    if stored.get('link_user_id'):
        return _finish_link(request, stored['link_user_id'], claims['sub'])

    user, error = _resolve_user(claims)
    if error:
        messages.error(request, error)
        return redirect(login_url)
    if not user.is_active:
        messages.error(request, '此帳號已停用，如有疑問請聯絡幹部。')
        return redirect(login_url)

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect(_safe_next(request, stored.get('next')))


def _finish_link(request, link_user_id, sub):
    """綁定流程的收尾：發起綁定的人必須仍是目前登入者，且這個 Google 帳號沒被別人綁走。"""
    profile_url = reverse('accounts:profile')
    if not request.user.is_authenticated or request.user.pk != link_user_id:
        messages.error(request, 'Google 帳號綁定失敗（登入狀態已改變），請重新操作。')
        return redirect(profile_url if request.user.is_authenticated else reverse('accounts:login'))

    owner = User.objects.filter(google_sub=sub).exclude(pk=request.user.pk).first()
    if owner:
        messages.error(request, '這個 Google 帳號已綁定在其他團員帳號上，無法重複綁定。')
        return redirect(profile_url)

    request.user.google_sub = sub
    request.user.save(update_fields=['google_sub'])
    logger.info('Google 帳號手動綁定：user=%s', request.user.pk)
    messages.success(request, '已綁定 Google 帳號，之後可直接用 Google 登入。')
    return redirect(profile_url)
