from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class Account(models.Model):
    ACCOUNT_TYPES = [
        ('checking', 'Checking'),
        ('savings', 'Savings'),
        ('credit_card', 'Credit Card'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Only for credit cards'
    )
    last_four = models.CharField(
        max_length=4, blank=True,
        help_text='Last 4 digits of card/account number'
    )
    color = models.CharField(max_length=7, default='#4F46E5', help_text='Hex color for UI display')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def available_credit(self):
        if self.account_type == 'credit_card' and self.credit_limit:
            return self.credit_limit - abs(self.balance)
        return None

    def recalculate_balance(self):
        """Recalculate balance from all transactions."""
        income = self.transactions.filter(
            transaction_type='income'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        expense = self.transactions.filter(
            transaction_type='expense'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        self.balance = income - expense
        self.save(update_fields=['balance'])


class Category(models.Model):
    CATEGORY_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('both', 'Both'),
    ]

    ICONS = [
        ('🏠', 'Housing'), ('🚗', 'Transport'), ('🍔', 'Food'), ('💊', 'Health'),
        ('🎮', 'Entertainment'), ('👕', 'Clothing'), ('🎓', 'Education'),
        ('💼', 'Work'), ('💰', 'Income'), ('🛒', 'Shopping'), ('✈️', 'Travel'),
        ('📱', 'Technology'), ('⚡', 'Utilities'), ('🎁', 'Gifts'), ('🐾', 'Pets'),
        ('⛽', 'Fuel'), ('🏪', 'Grocery'), ('💡', 'Other'), ('🏢', 'Insurance'),
        ('🎹', 'Piano'), ('🏊', 'Swimming'), ('💵', 'Subscriptions'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=50)
    category_type = models.CharField(max_length=10, choices=CATEGORY_TYPES, default='both')
    icon = models.CharField(max_length=5, default='💡')
    color = models.CharField(max_length=7, default='#6B7280')

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']
        unique_together = ['user', 'name']

    def __str__(self):
        return f"{self.icon} {self.name}"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        sign = '+' if self.transaction_type == 'income' else '-'
        return f"{sign}${self.amount} — {self.description} ({self.date})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.account.recalculate_balance()

    def delete(self, *args, **kwargs):
        account = self.account
        super().delete(*args, **kwargs)
        account.recalculate_balance()


class CategoryRule(models.Model):
    """Maps a description keyword/pattern to a category.
    Rules are evaluated in priority order (lower number = higher priority).
    Matching is case-insensitive. Use match_type to control exact vs contains vs starts/ends.
    """
    MATCH_TYPES = [
        ('contains',    'Contains'),
        ('exact',       'Exact match'),
        ('startswith',  'Starts with'),
        ('endswith',    'Ends with'),
        ('regex',       'Regex'),
    ]

    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='category_rules')
    keyword   = models.CharField(max_length=255, help_text='Text to match against the transaction description')
    match_type = models.CharField(max_length=12, choices=MATCH_TYPES, default='contains')
    category  = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='rules')
    min_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Optional — only match transactions with amount ≥ this value'
    )
    priority  = models.PositiveIntegerField(default=10, help_text='Lower number = evaluated first')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority', 'keyword']
        unique_together = ['user', 'keyword', 'match_type']

    def __str__(self):
        return f'"{self.keyword}" ({self.get_match_type_display()}) → {self.category}'

    def matches(self, description: str, amount=None) -> bool:
        """Return True if this rule matches the given description (and amount, if set)."""
        import re
        # Check amount threshold first — cheap early-exit
        if self.min_amount is not None and amount is not None:
            if amount < self.min_amount:
                return False
        desc = description.lower()
        kw   = self.keyword.lower()
        if self.match_type == 'contains':
            return kw in desc
        if self.match_type == 'exact':
            return desc == kw
        if self.match_type == 'startswith':
            return desc.startswith(kw)
        if self.match_type == 'endswith':
            return desc.endswith(kw)
        if self.match_type == 'regex':
            try:
                return bool(re.search(self.keyword, description, re.IGNORECASE))
            except re.error:
                return False
        return False


def apply_category_rules(user, queryset=None):
    """Apply all active CategoryRules for a user to a Transaction queryset.
    Returns (updated_count, skipped_count).
    If queryset is None, applies to ALL transactions for the user.
    Only updates transactions whose category is currently unset.
    """
    rules = CategoryRule.objects.filter(
        user=user, is_active=True
    ).select_related('category').order_by('priority', 'keyword')

    if queryset is None:
        queryset = Transaction.objects.filter(user=user)

    updated = 0
    for txn in queryset.select_related('category'):
        for rule in rules:
            if rule.matches(txn.description, amount=txn.amount):
                if txn.category_id != rule.category_id:
                    txn.category = rule.category
                    Transaction.objects.filter(pk=txn.pk).update(category=rule.category)
                    updated += 1
                break  # first matching rule wins

    return updated


class Budget(models.Model):
    """Monthly budget target for a category.
    A budget of e.g. $500 for 'Food & Dining' means you expect/allow
    $500 of spending (or income) in that category each month.
    """
    user     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets')
    amount   = models.DecimalField(max_digits=12, decimal_places=2,
                                   help_text='Monthly target amount (always positive)')
    notes    = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['category__name']
        unique_together = ['user', 'category']

    def __str__(self):
        return f"{self.category} — ${self.amount}/mo"
