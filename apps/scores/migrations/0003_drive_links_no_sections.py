from django.db import migrations, models
from django.db.models import ProtectedError

import apps.scores.models


def seed_instruments_and_reset_parts(apps, schema_editor):
    """
    1. 補上新的樂器：吉他族群（吉他／電吉他／Bass 吉他）與「其他（手填）」。
       只在**已有樂器資料**的資料庫做（Render 上）；全新資料庫是空的，樂器由
       fixtures/instruments.json 載入（已含同樣的資料，且主鍵一致），這裡不能先塞，否則會與 fixture 主鍵衝突。
    2. 清掉既有的分譜紀錄（總譜保留）。舊分譜是「樂器＋聲部＋上傳檔案」，檔案在 Render 重新部署時
       早已遺失，結構也和新的「每種樂器一個 Drive 連結」不同——owner 決定清掉重來，等譜務把連結貼上。
       被其他資料引用而刪不掉的（ProtectedError）保留不動。
    """
    Family = apps.get_model('accounts', 'InstrumentFamily')
    Type = apps.get_model('accounts', 'InstrumentType')
    Score = apps.get_model('scores', 'Score')

    if Family.objects.exists():
        guitar, _ = Family.objects.get_or_create(name='吉他', defaults={'category': 'other'})
        for name in ('吉他', '電吉他', 'Bass 吉他'):
            Type.objects.get_or_create(name=name, defaults={'family': guitar})
        other, _ = Family.objects.get_or_create(name='其他', defaults={'category': 'other'})
        Type.objects.get_or_create(name='其他（手填）', defaults={'family': other})

    for part in Score.objects.filter(score_type='part'):
        try:
            part.delete()
        except ProtectedError:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_alter_registration_options'),
        ('scores', '0002_score_full_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='score',
            name='drive_url',
            field=models.URLField(
                blank=True, max_length=500, verbose_name='Google Drive 連結',
                help_text='樂譜放在樂團的 Google Drive，這裡貼分享連結，團員由此下載。',
                validators=[apps.scores.models.validate_drive_url],
            ),
        ),
        migrations.AddField(
            model_name='score',
            name='custom_instrument_name',
            field=models.CharField(
                blank=True, max_length=100, verbose_name='樂器名稱（手填）',
                help_text='樂器選「其他（手填）」時必填，例如：手搖鈴。',
            ),
        ),
        migrations.RunPython(seed_instruments_and_reset_parts, migrations.RunPython.noop),
    ]
