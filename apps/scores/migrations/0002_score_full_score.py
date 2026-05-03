from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scores', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='score',
            name='full_score',
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={'score_type': 'full'},
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='parts',
                to='scores.score',
                verbose_name='所屬總譜',
            ),
        ),
    ]
