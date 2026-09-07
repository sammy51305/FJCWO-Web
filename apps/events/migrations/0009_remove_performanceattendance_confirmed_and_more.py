# 手寫調整過：自動產生的版本是「刪 confirmed、加 attended」與「直接刪 on_leave」，
# 兩者都會丟資料。改成 RenameField ＋ 資料搬遷，語意才對得上。
from django.db import migrations, models


def on_leave_to_intent(apps, schema_editor):
    """舊的 on_leave=True（核准過的演出請假）搬成新的 intent='declined'。

    廢除演出請假時，那些人的「我不參加」是真實表態過的資訊，不該隨著欄位一起消失。
    反向（intent → on_leave）不提供：三態塌回布林一定會遺失「待確認」與「不參加」的區別。
    """
    apps.get_model('events', 'PerformanceAttendance').objects.filter(
        on_leave=True
    ).update(intent='declined')


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0008_performanceattendance_on_leave_and_more"),
    ]

    operations = [
        # confirmed（事後到場）改名為 attended，避免與 intent='confirmed'（事前確認參加）
        # 望文生義撞在一起。用 RenameField 保住既有的到場紀錄。
        migrations.RenameField(
            model_name="performanceattendance",
            old_name="confirmed",
            new_name="attended",
        ),
        migrations.AlterField(
            model_name="performanceattendance",
            name="attended",
            field=models.BooleanField(
                default=False, help_text="演出當天事後登記", verbose_name="是否到場"
            ),
        ),
        migrations.AddField(
            model_name="performanceattendance",
            name="intent",
            field=models.CharField(
                choices=[
                    ("pending", "待確認"),
                    ("confirmed", "確認參加"),
                    ("declined", "不參加"),
                ],
                default="pending",
                help_text="團員事前表態；兩者都沒做的人維持「待確認」，由幹部聯繫",
                max_length=10,
                verbose_name="出席意願",
            ),
        ),
        migrations.AddField(
            model_name="performanceattendance",
            name="intent_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="表態時間"),
        ),
        migrations.AddField(
            model_name="performanceattendance",
            name="decline_reason",
            field=models.TextField(blank=True, verbose_name="無法參加的原因"),
        ),
        # 順序重要：先把 on_leave 的資訊搬進 intent，再刪欄位
        migrations.RunPython(on_leave_to_intent, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="performanceattendance",
            name="on_leave",
        ),
        migrations.DeleteModel(
            name="PerformanceLeaveRequest",
        ),
    ]
