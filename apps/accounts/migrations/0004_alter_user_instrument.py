from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_instrumentfamily_alter_instrumenttype'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='instrument',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='accounts.instrumentfamily',
                verbose_name='樂器',
            ),
        ),
    ]
