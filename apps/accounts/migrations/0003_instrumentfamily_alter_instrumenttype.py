from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_registration'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstrumentFamily',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='族群名稱')),
                ('category', models.CharField(
                    choices=[
                        ('woodwind', '木管'),
                        ('brass', '銅管'),
                        ('percussion', '打擊'),
                        ('other', '其他'),
                    ],
                    max_length=20,
                    verbose_name='分類',
                )),
            ],
            options={
                'verbose_name': '樂器族群',
                'verbose_name_plural': '樂器族群列表',
                'ordering': ['category', 'name'],
            },
        ),
        migrations.RemoveField(
            model_name='instrumenttype',
            name='category',
        ),
        migrations.AddField(
            model_name='instrumenttype',
            name='family',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='instruments',
                to='accounts.instrumentfamily',
                verbose_name='族群',
            ),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='instrumenttype',
            options={
                'ordering': ['family__category', 'family__name', 'name'],
                'verbose_name': '樂器',
                'verbose_name_plural': '樂器列表',
            },
        ),
    ]
