"""
Forecast engine for Ledger.

Strategy:
  For each future month we build a ForecastMonth that contains:
    - recurring_income / recurring_expense  (from is_recurring transactions)
    - budget_income / budget_expense        (from Budget objects)
    - projected_income / projected_expense  (max of recurring vs budget per category,
                                             then fallback to whichever exists)
    - category_rows                         (per-category breakdown)
    - running_balance                       (cumulative from current actual balance)

The caller chooses how many months ahead to show (default 6).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Optional


@dataclass
class CategoryForecastRow:
    category_id:   Optional[int]
    category_name: str
    category_icon: str
    category_color: str
    txn_type:      str          # 'income' or 'expense'

    recurring_amount: Decimal = Decimal('0')   # sum of recurring txns
    budget_amount:    Decimal = Decimal('0')   # budget target (0 if none set)
    projected_amount: Decimal = Decimal('0')   # final projected value

    @property
    def has_budget(self):
        return self.budget_amount > 0

    @property
    def variance(self):
        """Projected minus budget (positive = over budget for expenses)."""
        if not self.has_budget:
            return None
        return self.projected_amount - self.budget_amount


@dataclass
class ForecastMonth:
    year:  int
    month: int
    label: str          # e.g. "Apr 2025"

    category_rows: List[CategoryForecastRow] = field(default_factory=list)
    running_balance: Decimal = Decimal('0')

    @property
    def income_rows(self):
        return [r for r in self.category_rows if r.txn_type == 'income']

    @property
    def expense_rows(self):
        return [r for r in self.category_rows if r.txn_type == 'expense']

    @property
    def projected_income(self):
        return sum((r.projected_amount for r in self.income_rows), Decimal('0'))

    @property
    def projected_expense(self):
        return sum((r.projected_amount for r in self.expense_rows), Decimal('0'))

    @property
    def projected_net(self):
        return self.projected_income - self.projected_expense

    @property
    def budget_income(self):
        return sum((r.budget_amount for r in self.income_rows), Decimal('0'))

    @property
    def budget_expense(self):
        return sum((r.budget_amount for r in self.expense_rows), Decimal('0'))

    @property
    def budget_net(self):
        return self.budget_income - self.budget_expense

    @property
    def recurring_income(self):
        return sum((r.recurring_amount for r in self.income_rows), Decimal('0'))

    @property
    def recurring_expense(self):
        return sum((r.recurring_amount for r in self.expense_rows), Decimal('0'))


def _month_label(year: int, month: int) -> str:
    return date(year, month, 1).strftime('%b %Y')


def _advance_month(year: int, month: int, n: int = 1):
    """Return (year, month) advanced by n months."""
    month += n
    while month > 12:
        month -= 12
        year += 1
    return year, month


def build_forecast(user, months_ahead: int = 6) -> List[ForecastMonth]:
    """
    Build a forecast for `months_ahead` future months.

    Projection logic per category per month:
      - recurring_amount = sum of all is_recurring transactions in that category
      - budget_amount    = Budget.amount for that category (0 if none)
      - projected_amount:
          * If both exist  → use the larger of the two (conservative estimate)
          * If only recurring → use recurring
          * If only budget    → use budget
          * If neither        → row is excluded
    """
    from .models import Transaction, Budget, Category

    today = date.today()

    # ── 1. Collect all recurring transactions ────────────────────────────────
    recurring_txns = (
        Transaction.objects
        .filter(user=user, is_recurring=True)
        .select_related('category')
    )

    # Group by (category_id, txn_type) → sum of amounts
    recurring_by_cat = defaultdict(Decimal)   # key: (cat_id, txn_type)
    cat_meta = {}                              # cat_id → (name, icon, color)

    for txn in recurring_txns:
        key = (txn.category_id, txn.transaction_type)
        recurring_by_cat[key] += txn.amount
        if txn.category_id not in cat_meta:
            if txn.category:
                cat_meta[txn.category_id] = (
                    txn.category.name, txn.category.icon, txn.category.color
                )
            else:
                cat_meta[None] = ('Uncategorised', '💡', '#6B7280')

    # ── 2. Collect budgets ───────────────────────────────────────────────────
    budgets = Budget.objects.filter(user=user).select_related('category')

    budget_by_cat = {}   # cat_id → (amount, txn_type inferred from category_type)
    for b in budgets:
        # Infer whether this budget is income or expense from the category type
        # 'income' → income, anything else → expense
        txn_type = 'income' if b.category.category_type == 'income' else 'expense'
        budget_by_cat[b.category_id] = (b.amount, txn_type)
        if b.category_id not in cat_meta:
            cat_meta[b.category_id] = (b.category.name, b.category.icon, b.category.color)

    # ── 3. Union of all category keys ────────────────────────────────────────
    all_keys = set()
    for (cat_id, txn_type) in recurring_by_cat:
        all_keys.add((cat_id, txn_type))
    for cat_id, (_, txn_type) in budget_by_cat.items():
        all_keys.add((cat_id, txn_type))

    # ── 4. Current running balance (sum of all account balances) ─────────────
    from .models import Account
    from django.db.models import Sum
    balance_agg = Account.objects.filter(user=user, is_active=True).aggregate(
        total=Sum('balance')
    )
    running_balance = balance_agg['total'] or Decimal('0')

    # ── 5. Build months ──────────────────────────────────────────────────────
    result = []
    year, month = today.year, today.month
    year, month = _advance_month(year, month, 1)   # start from next month

    for _ in range(months_ahead):
        rows = []
        for (cat_id, txn_type) in sorted(all_keys, key=lambda k: cat_meta.get(k[0], ('',))[0]):
            rec_amt    = recurring_by_cat.get((cat_id, txn_type), Decimal('0'))
            bud_entry  = budget_by_cat.get(cat_id)
            bud_amt    = bud_entry[0] if bud_entry and bud_entry[1] == txn_type else Decimal('0')

            if rec_amt == 0 and bud_amt == 0:
                continue

            # Conservative projection: larger of recurring vs budget
            projected = max(rec_amt, bud_amt)

            name, icon, color = cat_meta.get(cat_id, ('Uncategorised', '💡', '#6B7280'))
            rows.append(CategoryForecastRow(
                category_id=cat_id,
                category_name=name,
                category_icon=icon,
                category_color=color,
                txn_type=txn_type,
                recurring_amount=rec_amt,
                budget_amount=bud_amt,
                projected_amount=projected,
            ))

        fm = ForecastMonth(year=year, month=month, label=_month_label(year, month),
                           category_rows=rows)

        running_balance += fm.projected_net
        fm.running_balance = running_balance
        result.append(fm)
        year, month = _advance_month(year, month)

    return result
