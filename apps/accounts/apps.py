from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'apps.accounts'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # 註冊登入失敗計數的訊號接收器
        from . import login_throttle  # noqa: F401
