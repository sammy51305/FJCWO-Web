from django.db import migrations


def wipe(apps, schema_editor):
    """
    藏譜改版（2026-10）：樂譜改成「一首曲子一筆藏譜」，分譜改掛在演出的族群資料夾，
    舊的總譜／分譜資料不搬移，全部清掉重建（owner 決定；當時只有測試站有資料）。
    引用樂譜的曲目單、分譜分配、樂譜交換紀錄都是 PROTECT／指向舊分譜，一併清除。

    刻意與後面的欄位變更分開成兩支：Postgres 不允許同一個交易裡刪列（有待處理的外鍵檢查）
    又 ALTER TABLE（見 0004 的說明）。
    """
    for model in [
        ('events', 'PartAssignment'),
        ('events', 'Setlist'),
        ('scores', 'ScoreExchangeItem'),
        ('scores', 'ScoreExchange'),
        ('scores', 'Score'),
    ]:
        apps.get_model(*model).objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scores', '0004_remove_score_section_file'),
        ('events', '0009_remove_performanceattendance_confirmed_and_more'),
    ]

    operations = [
        migrations.RunPython(wipe, migrations.RunPython.noop),
    ]
