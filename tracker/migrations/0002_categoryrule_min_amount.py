from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='categoryrule',
            name='min_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Optional — only match transactions with amount ≥ this value',
                max_digits=12,
                null=True,
            ),
        ),
    ]
