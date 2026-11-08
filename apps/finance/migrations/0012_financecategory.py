import apps.finance.models
from django.db import migrations, models

# (代碼, 名稱, 適用, 排序, 系統分類)
# 前 8 個沿用原本寫死的分類代碼，舊紀錄的 category 欄值不用動。
# 後 2 個（贊助／捐款、幹部代墊／借款）是這次新增的收入來源；之後的增減由幹部在後台自己來。
DEFAULT_CATEGORIES = [
    ('venue', '場地費', 'both', 10, False),
    ('instructor', '師資費', 'both', 20, False),
    ('instrument_purchase', '樂器購置費', 'both', 30, False),
    ('instrument_maintenance', '樂器保養費', 'both', 40, False),
    ('score', '樂譜費', 'both', 50, False),
    ('insurance', '保險費', 'both', 60, False),
    ('membership', '會費', 'income', 70, True),
    ('sponsorship', '贊助／捐款', 'income', 80, False),
    ('officer_advance', '幹部代墊／借款', 'both', 90, False),
    ('other', '其他', 'both', 999, False),
]


def seed_categories(apps, schema_editor):
    FinanceCategory = apps.get_model('finance', 'FinanceCategory')
    FinanceRecord = apps.get_model('finance', 'FinanceRecord')
    for code, name, kind, order, is_system in DEFAULT_CATEGORIES:
        if code == 'membership' and FinanceRecord.objects.filter(
                category='membership', type='expense').exists():
            kind = 'both'      # 舊資料裡竟有「會費」支出：不收窄適用範圍，免得這幾筆編輯時被擋
        FinanceCategory.objects.get_or_create(
            code=code,
            defaults={'name': name, 'kind': kind, 'sort_order': order, 'is_system': is_system},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0011_feeperiod_student_amount'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinanceCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(default=apps.finance.models._new_category_code, editable=False, max_length=30, unique=True, verbose_name='代碼')),
                ('name', models.CharField(max_length=30, unique=True, verbose_name='名稱')),
                ('kind', models.CharField(choices=[('income', '僅收入'), ('expense', '僅支出'), ('both', '收入與支出皆可')], default='both', max_length=10, verbose_name='適用')),
                ('sort_order', models.PositiveIntegerField(default=100, help_text='數字小的排前面', verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, help_text='取消勾選＝新增收支時不再列出，舊紀錄不受影響', verbose_name='啟用')),
                ('is_system', models.BooleanField(default=False, editable=False, verbose_name='系統分類')),
            ],
            options={
                'verbose_name': '收支分類',
                'verbose_name_plural': '收支分類列表',
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
