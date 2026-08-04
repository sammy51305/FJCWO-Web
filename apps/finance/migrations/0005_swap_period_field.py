"""
交換期別欄位（附錄五 §9 P1，接續 0004 資料搬遷）：
移除舊的 period（自由文字）、把 period_ref 改名為 period 並設為必填 PROTECT。
執行到這裡時，每筆 MembershipFee 的 period_ref 都已由 0004 填好，不會有 NULL。
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0004_migrate_period_to_feeperiod'),
    ]

    operations = [
        # 先解除舊的 (member, period[自由文字]) 唯一限制，才能移除舊欄位
        migrations.AlterUniqueTogether(
            name='membershipfee',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='membershipfee',
            name='period',
        ),
        migrations.RenameField(
            model_name='membershipfee',
            old_name='period_ref',
            new_name='period',
        ),
        migrations.AlterField(
            model_name='membershipfee',
            name='period',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='fees', to='finance.feeperiod', verbose_name='期別',
            ),
        ),
        migrations.AlterModelOptions(
            name='membershipfee',
            options={
                'ordering': ['-period__year', '-period__term', 'member__name'],
                'verbose_name': '會費繳納紀錄',
                'verbose_name_plural': '會費繳納紀錄列表',
            },
        ),
        migrations.AlterUniqueTogether(
            name='membershipfee',
            unique_together={('member', 'period')},
        ),
    ]
