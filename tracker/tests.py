from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Account, Category, Reconciliation, Transaction


class ReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='password')
        self.client.login(username='tester', password='password')
        self.checking = Account.objects.create(
            user=self.user, name='Checking', account_type='checking'
        )
        self.savings = Account.objects.create(
            user=self.user, name='Savings', account_type='savings'
        )
        self.other = Account.objects.create(
            user=self.user, name='Other', account_type='checking'
        )

    def transaction(self, account, transaction_type, description, amount='100.00'):
        return Transaction.objects.create(
            user=self.user,
            account=account,
            transaction_type=transaction_type,
            description=description,
            amount=Decimal(amount),
            date=date(2026, 8, 1),
        )

    def test_matches_cross_account_opposite_amounts_and_excludes_from_reports(self):
        expense = self.transaction(self.checking, 'expense', 'Transfer out')
        income = self.transaction(self.savings, 'income', 'Transfer in')

        response = self.client.get(reverse('reconciliation_list'))
        self.assertContains(response, 'Transfer out')
        self.assertContains(response, 'Transfer in')
        self.assertNotContains(response, 'Same account')
        self.assertNotContains(response, 'Different amount')

        response = self.client.post(reverse('reconciliation_list'), {
            'transaction_a': expense.pk,
            'transaction_b': income.pk,
        })

        self.assertRedirects(response, reverse('reconciliation_list'))
        self.assertEqual(Reconciliation.objects.count(), 1)
        reconciled = Category.objects.get(user=self.user, name='Reconciled')
        expense.refresh_from_db()
        income.refresh_from_db()
        self.assertEqual(expense.category_id, reconciled.pk)
        self.assertEqual(income.category_id, reconciled.pk)

        matched_tab = self.client.get(
            reverse('reconciliation_list'), {'tab': 'matched'}
        )
        self.assertContains(matched_tab, 'Transfer out')
        self.assertContains(matched_tab, 'Transfer in')
        self.assertContains(matched_tab, 'Unmatch')

        response = self.client.post(reverse('reconciliation_list'), {
            'action': 'unmatch',
            'reconciliation_id': Reconciliation.objects.get().pk,
        })
        self.assertRedirects(
            response, f"{reverse('reconciliation_list')}?tab=matched"
        )
        self.assertEqual(Reconciliation.objects.count(), 0)
        unmatched_tab = self.client.get(reverse('reconciliation_list'))
        self.assertContains(unmatched_tab, 'Transfer out')
        self.assertContains(unmatched_tab, 'Transfer in')

        transaction_list = self.client.get(reverse('transaction_list'))
        self.assertEqual(transaction_list.context['total_income'], Decimal('100'))
        self.assertEqual(transaction_list.context['total_expense'], Decimal('100'))

        report = self.client.get(reverse('reports'), {'year': 2026, 'month': 8})
        self.assertEqual(report.context['income_total'], Decimal('100'))
        self.assertEqual(report.context['expense_total'], Decimal('100'))

    def test_starting_balance_is_the_base_for_account_balance(self):
        account = Account.objects.create(
            user=self.user,
            name='Opening Balance Account',
            account_type='checking',
            starting_balance=Decimal('250.00'),
        )
        account.recalculate_balance()
        self.assertEqual(account.balance, Decimal('250.00'))

        self.transaction(account, 'income', 'Deposit', '100.00')
        self.transaction(account, 'expense', 'Purchase', '40.00')
        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal('310.00'))

        response = self.client.post(reverse('account_edit', args=[account.pk]), {
            'name': account.name,
            'account_type': account.account_type,
            'starting_balance': '500.00',
            'credit_limit': '',
            'last_four': '',
            'color': account.color,
        })
        self.assertRedirects(response, reverse('account_list'))
        account.refresh_from_db()
        self.assertEqual(account.starting_balance, Decimal('500.00'))
        self.assertEqual(account.balance, Decimal('560.00'))
