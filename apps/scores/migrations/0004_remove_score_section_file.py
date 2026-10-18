from django.db import migrations


class Migration(migrations.Migration):
    """
    移除 Score.section 與 Score.file。

    刻意與 0003 分開：0003 會刪除重複的分譜（資料變更），Postgres 不允許同一個交易裡
    「有待處理的觸發事件（刪除列的外鍵檢查）」又 ALTER TABLE，合併成一支會在已有資料的
    資料庫（Render）上失敗（cannot ALTER TABLE ... because it has pending trigger events）。
    """

    dependencies = [
        ('scores', '0003_drive_links_no_sections'),
    ]

    operations = [
        migrations.RemoveField(model_name='score', name='section'),
        migrations.RemoveField(model_name='score', name='file'),
    ]
