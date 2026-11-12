import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_temp_password_email(user, username, password):
    """
    寄送帳號與臨時密碼給新建立的團員。
    寄信失敗不應擋住帳號建立本身（帳號已經建立成功），所以失敗只記 log，
    呼叫端仍需把帳密顯示在畫面上給幹部，作為寄信失敗時的備援管道。
    回傳 True/False 表示是否寄送成功。
    """
    subject = '【百韻管樂團】您的帳號已建立'
    # 網址取自 settings.SITE_URL（.env 的 SITE_URL），換網址只改 .env；沒設就不附，不猜網址
    login_line = f'登入網址：{settings.SITE_URL}{settings.LOGIN_URL}\n' if settings.SITE_URL else ''
    message = (
        f'{user.name} 您好，\n\n'
        f'幹部已為您建立百韻管樂團系統帳號：\n'
        f'{login_line}'
        f'帳號：{username}\n'
        f'臨時密碼：{password}\n\n'
        f'請使用以上帳密登入系統，登入後會要求您立即設定新密碼。\n'
    )
    try:
        send_mail(subject, message, None, [user.email], fail_silently=False)
        return True
    except Exception as e:
        logger.warning('寄送帳號密碼信件失敗（%s）：%s', user.email, e)
        return False
