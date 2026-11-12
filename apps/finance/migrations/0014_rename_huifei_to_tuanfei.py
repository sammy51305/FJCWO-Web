"""「會費」全面改稱「團費」，與團練紀錄試算表的用詞一致。

- FeePeriod / MembershipFee 的 verbose_name（只影響後台顯示）。
- 系統收入分類 membership 的名稱：0012 建的是「會費」，這裡改成「團費」。
  只在名稱還是「會費」時改，幹部若在後台另外取過名就不動（系統分類理論上不能改名，保險而已）。
已寫入的收支明細描述（如「某某（2026 下期）會費」）是當時的紀錄，不回頭改。
"""

from django.db import migrations


def rename_category(apps, schema_editor):
    FinanceCategory = apps.get_model('finance', 'FinanceCategory')
    FinanceCategory.objects.filter(code='membership', name='會費').update(name='團費')


def restore_category(apps, schema_editor):
    FinanceCategory = apps.get_model('finance', 'FinanceCategory')
    FinanceCategory.objects.filter(code='membership', name='團費').update(name='會費')


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0013_financerecord_category_fk'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='feeperiod',
            options={'ordering': ['-year', 'term'], 'verbose_name': '團費期別', 'verbose_name_plural': '團費期別列表'},
        ),
        migrations.AlterModelOptions(
            name='membershipfee',
            options={'ordering': ['-period__year', '-period__term', 'member__name'], 'verbose_name': '團費收繳紀錄', 'verbose_name_plural': '團費收繳紀錄列表'},
        ),
        migrations.RunPython(rename_category, restore_category),
    ]
