from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0005_remove_transaction_is_recurring_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reconciliation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('transaction_a', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reconciliation_a', to='tracker.transaction')),
                ('transaction_b', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reconciliation_b', to='tracker.transaction')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]