from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-)fcwve=n7xb1cg26twc!(#wlz2xv0z#)4bl6hh91%61mzdigp6')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost 127.0.0.1').split()

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 本地 apps
    'apps.accounts',
    'apps.events',
    'apps.scores',
    'apps.assets',
    'apps.finance',
    'apps.notifications',
    'apps.meetings',
    'apps.announcements',
    'apps.public',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise 讓 Django 自己供應 static 檔案（PaaS 上沒有 Nginx 可用）。
    # 位置固定在 SecurityMiddleware 之後、其餘全部之前，這是官方要求的順序。
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.accounts.middleware.ForcePasswordChangeMiddleware',
    'apps.public.middleware.NoIndexMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# 資料庫有兩種設定來源，本機與雲端各走一邊：
#   - 本機開發：沿用 DB_NAME / DB_USER / ... 五個變數（見 .env.example）
#   - 雲端部署：託管 Postgres（Neon、Render 等）給的是一條 DATABASE_URL 連線字串，
#     設了它就整包蓋過上面五個變數。conn_max_age 讓連線重用，免得每個 request 都重連；
#     ssl_require 是託管資料庫的硬性要求。
if os.environ.get('DATABASE_URL'):
    import dj_database_url

    DATABASES = {
        'default': dj_database_url.parse(
            os.environ['DATABASE_URL'], conn_max_age=600, ssl_require=True
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'fjcwo'),
            'USER': os.environ.get('DB_USER', 'fjcwo_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hant'
TIME_ZONE = 'Asia/Taipei'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise 的壓縮儲存：collectstatic 時一併產生 .gz/.br。
# 刻意不用帶 manifest 的版本——manifest 會在檔名加雜湊，少一個檔案就整頁 500，
# 對測試站來說風險大於快取效益。
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# 雲端部署時必填：POST 表單的來源網域白名單（含 scheme，如 https://fjcwo.onrender.com）。
# 沒填會讓所有表單送出被擋成 CSRF 403。
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split() if o
]

# ── 正式／測試站的安全設定 ────────────────────────────────────────────
# 全部以環境變數開關、預設關閉：本機開發與測試不受影響（測試時 Django 會把 DEBUG
# 設為 False，若改用 `if not DEBUG` 判斷，SSL 轉址會讓整套測試被 301 打掛）。
# 部署時在平台上把這兩個設為 True。
if os.environ.get('DJANGO_SECURE_SSL_REDIRECT', 'False') == 'True':
    SECURE_SSL_REDIRECT = True
    # PaaS 在反向代理層終結 TLS，Django 自己看到的是 http，
    # 靠這個 header 才知道使用者其實走的是 https，否則會無限轉址。
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if os.environ.get('DJANGO_SECURE_COOKIES', 'False') == 'True':
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# 敏感個資（身分證字號／住址／出生年月日）的欄位加密金鑰（#13-1 決定二）。
# 內容可以是任意字串，程式會用 SHA-256 推導出真正的 Fernet key（見 apps/accounts/fields.py）。
#
# 沒設就退回開發用預設值，本機與測試跑得動——**但那把公開在 repo 裡，等於沒加密**。
# 任何存放真實個資的環境都必須設，`build.sh` 部署時會擋下沒設的情況。
# 換金鑰會讓既有密文解不開（顯示為空），要換必須先解密再重新加密。
FIELD_ENCRYPTION_SECRET = os.environ.get(
    'DJANGO_FIELD_ENCRYPTION_KEY', 'insecure-dev-key-do-not-use-in-production'
)

# 測試站設 True：robots.txt 改為整站禁止，並在每個回應加上 X-Robots-Tag: noindex。
# 正式站維持 False，讓公開頁（關於百韻、組織章程、公開公告）搜尋得到。
ROBOTS_NOINDEX = os.environ.get('DJANGO_ROBOTS_NOINDEX', 'False') == 'True'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@fjcwo.local')

# 沒有設定 SMTP 帳密時（本機開發預設如此），改用 console backend，
# 寄信內容直接印在終端機，不會因為缺少憑證而噴錯或卡住。
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
