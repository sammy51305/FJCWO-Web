"""敏感個資的欄位層級加密（#13-1 決定二，2026-09-08 定案）。

**加密什麼**：身分證字號／居留證號、住址、出生年月日這三個欄位，其餘不動。

**為什麼要加密**：正式站傾向放雲端，資料庫在他人機器上、金鑰放平台環境變數，
兩者分離時加密才有實質意義（若走家機自架、金鑰與 DB 同機，防護力接近零，見 DESIGN #10）。
真正防的是「DB 或備份檔外流」，頁面上的曝光由可見範圍（決定一）負責，兩者互補不重疊。

**用 Fernet（對稱加密）而非雜湊**：這些值要能還原——申報要列出完整號碼、
團員自己要看得到、幹部詳情頁要展開。雜湊不可逆，做不到這些。

**金鑰從任意字串推導**：`SHA-256(secret)` 取 32 bytes 再 base64，所以環境變數填什麼字串都行，
不必產生格式正確的 Fernet key。這讓 Render 的 `generateValue` 可以直接用，
也少一種「金鑰格式錯誤導致整站起不來」的失敗模式。

**代價（已知並接受）**：加密欄位無法做 DB 層 unique、無法用 SQL 搜尋或排序。
這三個欄位目前都只用於顯示，沒有查詢需求；日後若要依生日排序，得在 Python 端做
（團員數量級是數百，可接受）。
"""

import base64
import datetime as dt
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def _fernet():
    secret = settings.FIELD_ENCRYPTION_SECRET
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_value(raw: str) -> str:
    """加密成可放進 text 欄位的字串。空值維持空字串——空的東西沒有保護價值，
    而且讓「沒填」在 DB 裡仍然看得出來，避免每一列都長得像有資料。"""
    if raw in (None, ''):
        return ''
    return _fernet().encrypt(str(raw).encode()).decode()


def decrypt_value(stored: str) -> str:
    """解密。遇到解不開的值回傳空字串而不是炸掉——換過金鑰或手動改過 DB 時，
    整個團員列表不該因為一筆壞資料就 500；壞的那筆顯示為空，其餘照常。"""
    if stored in (None, ''):
        return ''
    try:
        return _fernet().decrypt(stored.encode()).decode()
    except (InvalidToken, ValueError):
        return ''


class EncryptedTextField(models.TextField):
    """存進 DB 前加密、讀出來自動解密的文字欄位。

    對 view、template、form 而言與一般文字欄位無異——加解密只發生在 DB 邊界。

    **DB 端不能限長度**（密文比原文長且長度不定），所以改用 `form_max_length`
    在表單層擋過長輸入，原本 CharField 的 `max_length` 語意由它承接。
    """

    def __init__(self, *args, form_max_length=None, **kwargs):
        self.form_max_length = form_max_length
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.form_max_length is not None:
            kwargs['form_max_length'] = self.form_max_length
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        return decrypt_value(value)

    def to_python(self, value):
        return value if value is None else str(value)

    def get_prep_value(self, value):
        if value in (None, ''):
            return ''
        return encrypt_value(value)

    def formfield(self, **kwargs):
        # 底層雖是 TextField（密文長度不定），但這些欄位是單行資料，
        # 不要繼承 TextField 預設的 textarea。
        from django import forms
        return models.Field.formfield(self, **{
            'form_class': forms.CharField, 'max_length': self.form_max_length, **kwargs
        })


class EncryptedDateField(EncryptedTextField):
    """加密的日期欄位：DB 存密文，Python 端仍然拿到 `datetime.date`。

    因為 DB 裡是密文，**不能用 SQL 依日期排序或篩選**（如「找出這個月生日的人」）。
    目前沒有這種需求；真要做就在 Python 端算。
    """

    def from_db_value(self, value, expression, connection):
        raw = decrypt_value(value)
        if not raw:
            return None
        try:
            return dt.date.fromisoformat(raw)
        except ValueError:
            return None

    def to_python(self, value):
        if value in (None, ''):
            return None
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        try:
            return dt.date.fromisoformat(str(value))
        except ValueError:
            raise ValidationError('日期格式錯誤（請用 YYYY-MM-DD）。')

    def get_prep_value(self, value):
        value = self.to_python(value)
        if value is None:
            return ''
        return encrypt_value(value.isoformat())

    def formfield(self, **kwargs):
        from django import forms
        return models.Field.formfield(self, **{
            'form_class': forms.DateField,
            'widget': forms.DateInput(attrs={'type': 'date'}),
            **kwargs,
        })
