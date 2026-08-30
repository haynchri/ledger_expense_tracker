from decimal import Decimal

from django.db import migrations, models


def preserve_existing_balances(apps, schema_editor):
    Account = apps.get_model('tracker', 'Account')
    Transaction = apps.get_model('tracker', 'Transaction')

    for account in Account.objects.all():
        income = sum(
            (amount for amount, in Transaction.objects.filter(
                account_id=account.pk, transaction_type='income'
            ).values_list('amount')),
            Decimal('0.00'),
        )
        expense = sum(
            (amount for amount, in Transaction.objects.filter(
                account_id=account.pk, transaction_type='expense'
            ).values_list('amount')),
            Decimal('0.00'),
        )
        account.starting_balance = account.balance - income + expense
        account.save(update_fields=['starting_balance'])


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_reconciliation'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='starting_balance',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12),
        ),
        migrations.RunPython(preserve_existing_balances, migrations.RunPython.noop),
    ]