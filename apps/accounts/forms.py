from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import User


class BootstrapAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def confirm_login_allowed(self, user):
        # 槍手（role=guest）是純名冊人物，一律不可登入系統（見 DESIGN 附錄五 §5 資安守則）。
        # 顯式擋在認證層，不依賴「槍手剛好沒有可用密碼」這種隱性前提；日後若對個別槍手
        # 開放登入（方案 b），再放行被開通者即可。
        if user.role == User.Role.GUEST:
            raise forms.ValidationError('此帳號無法登入系統。', code='guest_no_login')
        super().confirm_login_allowed(user)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'email', 'phone', 'instrument', 'section', 'grad_year']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'instrument': forms.Select(attrs={'class': 'form-select'}),
            'section': forms.Select(attrs={'class': 'form-select'}),
            'grad_year': forms.NumberInput(attrs={'class': 'form-control'}),
        }
