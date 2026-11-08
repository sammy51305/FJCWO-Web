import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """FinanceRecord.category：CharField(choices) → 指向 FinanceCategory.code 的外鍵。

    db_column 維持 'category'，資料庫裡的值（venue、membership…）原封不動，
    只是多了一道外鍵約束。0012 已把這些代碼都建成分類，所以約束一定成立。
    """

    dependencies = [
        ('finance', '0012_financecategory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='financerecord',
            name='category',
            field=models.ForeignKey(
                db_column='category', on_delete=django.db.models.deletion.PROTECT,
                related_name='records', to='finance.financecategory', to_field='code',
                verbose_name='分類',
            ),
        ),
    ]
