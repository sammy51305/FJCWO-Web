"""
會費期別轉檔（附錄五 §9 P1）：把 MembershipFee.period（自由文字，如「2026上半年」）
搬遷成 FeePeriod（結構化年份+期），並依 paid_at 設定 status。

非破壞性：既有繳費紀錄一筆不刪，只是改指向新建的期別主檔。
"""
import re

from django.db import migrations


def forwards(apps, schema_editor):
    FeePeriod = apps.get_model('finance', 'FeePeriod')
    MembershipFee = apps.get_model('finance', 'MembershipFee')

    for fee in MembershipFee.objects.all():
        raw = (fee.period or '').strip()
        m = re.search(r'\d{4}', raw)
        year = int(m.group()) if m else 2026
        # 「上」→ 上期，其餘（含「下」）→ 下期
        term = 'first' if '上' in raw else 'second'
        period, _ = FeePeriod.objects.get_or_create(
            year=year, term=term,
            defaults={'amount': fee.amount or 1},
        )
        fee.period_ref = period
        # 舊資料只有 paid_at 有無兩態：有 → 已繳，無 → 應繳未繳
        fee.status = 'paid' if fee.paid_at else 'unpaid'
        fee.save(update_fields=['period_ref', 'status'])


def backwards(apps, schema_editor):
    # 還原：把 period_ref 清空即可（period 自由文字仍在，尚未移除）
    MembershipFee = apps.get_model('finance', 'MembershipFee')
    MembershipFee.objects.update(period_ref=None)


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_membershipfee_status_alter_membershipfee_amount_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
