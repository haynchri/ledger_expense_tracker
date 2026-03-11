from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('account_type', models.CharField(choices=[('checking', 'Checking'), ('savings', 'Savings'), ('credit_card', 'Credit Card')], max_length=20)),
                ('balance', models.DecimalField(decimal_places=2, default='0.00', max_digits=12)),
                ('credit_limit', models.DecimalField(blank=True, decimal_places=2, help_text='Only for credit cards', max_digits=12, null=True)),
                ('last_four', models.CharField(blank=True, help_text='Last 4 digits of card/account number', max_length=4)),
                ('color', models.CharField(default='#4F46E5', help_text='Hex color for UI display', max_length=7)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('category_type', models.CharField(choices=[('income', 'Income'), ('expense', 'Expense'), ('both', 'Both')], default='both', max_length=10)),
                ('icon', models.CharField(default='💡', max_length=5)),
                ('color', models.CharField(default='#6B7280', max_length=7)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='categories', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name_plural': 'categories', 'ordering': ['name'], 'unique_together': {('user', 'name')}},
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('income', 'Income'), ('expense', 'Expense')], max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('description', models.CharField(max_length=255)),
                ('date', models.DateField(default=django.utils.timezone.now)),
                ('notes', models.TextField(blank=True)),
                ('receipt', models.FileField(blank=True, null=True, upload_to='receipts/')),
                ('is_recurring', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='tracker.account')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions', to='tracker.category')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-date', '-created_at']},
        ),
        migrations.CreateModel(
            name='CategoryRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(help_text='Text to match against the transaction description', max_length=255)),
                ('match_type', models.CharField(choices=[('contains', 'Contains'), ('exact', 'Exact match'), ('startswith', 'Starts with'), ('endswith', 'Ends with'), ('regex', 'Regex')], default='contains', max_length=12)),
                ('priority', models.PositiveIntegerField(default=10, help_text='Lower number = evaluated first')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rules', to='tracker.category')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='category_rules', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['priority', 'keyword'], 'unique_together': {('user', 'keyword', 'match_type')}},
        ),
    ]
