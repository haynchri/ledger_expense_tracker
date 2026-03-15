import csv
import io
import json
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone

from .models import Account, Category, Transaction
from .forms import (
    AccountForm, CategoryForm, TransactionForm,
    TransactionFilterForm, CSVImportForm
)


# ── Auth ──────────────────────────────────────────────────────────────────────

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            _create_default_data(user)
            login(request, user)
            messages.success(request, 'Welcome! Your account has been created.')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'tracker/register.html', {'form': form})


def _create_default_data(user):
    """Seed sensible defaults for new users."""
    default_categories = [
        ('Housing', 'expense', '🏠', '#EF4444'),
        ('Transport', 'expense', '🚗', '#F97316'),
        ('Food & Dining', 'expense', '🍔', '#EAB308'),
        ('Entertainment', 'expense', '🎮', '#8B5CF6'),
        ('Shopping', 'expense', '🛒', '#EC4899'),
        ('Health', 'expense', '💊', '#10B981'),
        ('Utilities', 'expense', '⚡', '#6B7280'),
        ('Salary', 'income', '💰', '#22C55E'),
        ('Freelance', 'income', '💼', '#3B82F6'),
        ('Other Income', 'income', '💡', '#14B8A6'),
    ]
    for name, cat_type, icon, color in default_categories:
        Category.objects.create(user=user, name=name, category_type=cat_type, icon=icon, color=color)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    accounts = Account.objects.filter(user=request.user, is_active=True)
    today = date.today()
    month_start = today.replace(day=1)

    monthly_income = Transaction.objects.filter(
        user=request.user, transaction_type='income',
        date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    monthly_expense = Transaction.objects.filter(
        user=request.user, transaction_type='expense',
        date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).select_related('account', 'category')[:10]

    # Build 6-month chart data
    chart_data = _get_monthly_chart_data(request.user, months=6)

    # Spending by category this month
    category_spending = Transaction.objects.filter(
        user=request.user, transaction_type='expense',
        date__gte=month_start
    ).values(
        'category__name', 'category__color', 'category__icon'
    ).annotate(total=Sum('amount')).order_by('-total')[:6]

    context = {
        'accounts': accounts,
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'net': monthly_income - monthly_expense,
        'recent_transactions': recent_transactions,
        'chart_data_json': json.dumps(chart_data),
        'category_spending': list(category_spending),
    }
    return render(request, 'tracker/dashboard.html', context)


def _get_monthly_chart_data(user, months=6):
    today = date.today()
    labels, income_data, expense_data = [], [], []
    for i in range(months - 1, -1, -1):
        # Go back i months
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        inc = Transaction.objects.filter(
            user=user, transaction_type='income',
            date__gte=month_start, date__lte=month_end
        ).aggregate(t=Sum('amount'))['t'] or 0

        exp = Transaction.objects.filter(
            user=user, transaction_type='expense',
            date__gte=month_start, date__lte=month_end
        ).aggregate(t=Sum('amount'))['t'] or 0

        labels.append(month_start.strftime('%b %Y'))
        income_data.append(float(inc))
        expense_data.append(float(exp))

    return {'labels': labels, 'income': income_data, 'expenses': expense_data}


# ── Accounts ──────────────────────────────────────────────────────────────────

@login_required
def account_list(request):
    accounts = Account.objects.filter(user=request.user, is_active=True)
    return render(request, 'tracker/account_list.html', {'accounts': accounts})


@login_required
def account_create(request):
    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            messages.success(request, f'Account "{account.name}" created.')
            return redirect('account_list')
    else:
        form = AccountForm()
    return render(request, 'tracker/account_form.html', {'form': form, 'title': 'Add Account'})


@login_required
def account_edit(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account updated.')
            return redirect('account_list')
    else:
        form = AccountForm(instance=account)
    return render(request, 'tracker/account_form.html', {'form': form, 'title': 'Edit Account', 'account': account})


@login_required
def account_delete(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    if request.method == 'POST':
        account.is_active = False
        account.save()
        messages.success(request, f'Account "{account.name}" removed.')
        return redirect('account_list')
    return render(request, 'tracker/confirm_delete.html', {'obj': account, 'type': 'Account'})


@login_required
def account_detail(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    transactions = Transaction.objects.filter(account=account).select_related('category')
    return render(request, 'tracker/account_detail.html', {
        'account': account,
        'transactions': transactions,
    })


# ── Categories ────────────────────────────────────────────────────────────────

@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user)
    return render(request, 'tracker/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.save()
            messages.success(request, f'Category "{cat.name}" created.')
            return redirect('category_list')
    else:
        form = CategoryForm()
    return render(request, 'tracker/category_form.html', {'form': form, 'title': 'Add Category'})


@login_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated.')
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'tracker/category_form.html', {'form': form, 'title': 'Edit Category'})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted.')
        return redirect('category_list')
    return render(request, 'tracker/confirm_delete.html', {'obj': category, 'type': 'Category'})


# ── Transactions ──────────────────────────────────────────────────────────────

@login_required
def transaction_list(request):
    from django.core.paginator import Paginator
    qs = Transaction.objects.filter(user=request.user).select_related('account', 'category')
    filter_form = TransactionFilterForm(request.user, request.GET)

    if filter_form.is_valid():
        d = filter_form.cleaned_data
        if d.get('account'):
            qs = qs.filter(account=d['account'])
        if d.get('category'):
            qs = qs.filter(category=d['category'])
        if d.get('transaction_type'):
            qs = qs.filter(transaction_type=d['transaction_type'])
        if d.get('date_from'):
            qs = qs.filter(date__gte=d['date_from'])
        if d.get('date_to'):
            qs = qs.filter(date__lte=d['date_to'])
        if d.get('search'):
            qs = qs.filter(description__icontains=d['search'])

    # Totals apply to the full filtered set, not just the current page
    total_income = qs.filter(transaction_type='income').aggregate(t=Sum('amount'))['t'] or 0
    total_expense = qs.filter(transaction_type='expense').aggregate(t=Sum('amount'))['t'] or 0

    # Pagination — default 25 rows, user can override with ?per_page=
    try:
        per_page = int(request.GET.get('per_page', 25))
        per_page = per_page if per_page in (10, 25, 50, 100) else 25
    except (ValueError, TypeError):
        per_page = 25

    paginator = Paginator(qs, per_page)
    page_num  = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_num)
    except Exception:
        page_obj = paginator.page(1)

    # Build a query string that preserves all filters but strips 'page'
    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    filter_qs = get_copy.urlencode()

    return render(request, 'tracker/transaction_list.html', {
        'transactions':  page_obj,
        'page_obj':      page_obj,
        'paginator':     paginator,
        'filter_qs':     filter_qs,
        'per_page':      per_page,
        'filter_form':   filter_form,
        'total_income':  total_income,
        'total_expense': total_expense,
        'net':           total_income - total_expense,
    })


@login_required
def transaction_create(request):
    if request.method == 'POST':
        form = TransactionForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.save()
            messages.success(request, 'Transaction added.')
            return redirect('transaction_list')
    else:
        form = TransactionForm(request.user)
    return render(request, 'tracker/transaction_form.html', {'form': form, 'title': 'Add Transaction'})


@login_required
def transaction_edit(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TransactionForm(request.user, request.POST, request.FILES, instance=txn)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transaction updated.')
            return redirect('transaction_list')
    else:
        form = TransactionForm(request.user, instance=txn)
    return render(request, 'tracker/transaction_form.html', {'form': form, 'title': 'Edit Transaction', 'txn': txn})


@login_required
def transaction_delete(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        txn.delete()
        messages.success(request, 'Transaction deleted.')
        return redirect('transaction_list')
    return render(request, 'tracker/confirm_delete.html', {'obj': txn, 'type': 'Transaction'})


# ── CSV Import / Export ───────────────────────────────────────────────────────

@login_required
def csv_export(request):
    qs = Transaction.objects.filter(user=request.user).select_related('account', 'category')

    # Apply same filters as list view
    account_id = request.GET.get('account')
    txn_type = request.GET.get('transaction_type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if account_id:
        qs = qs.filter(account_id=account_id)
    if txn_type:
        qs = qs.filter(transaction_type=txn_type)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'

    writer = csv.writer(response)
    writer.writerow(['date', 'type', 'account', 'category', 'description', 'amount', 'notes', 'recurring'])
    for t in qs:
        writer.writerow([
            t.date, t.transaction_type,
            t.account.name,
            t.category.name if t.category else '',
            t.description, t.amount, t.notes, t.is_recurring
        ])
    return response


@login_required
def csv_import(request):
    """Step 1 — choose account and upload the CSV file."""
    from .forms import CSVUploadForm
    if request.method == 'POST':
        form = CSVUploadForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            account  = form.cleaned_data['account']
            try:
                raw = csv_file.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                csv_file.seek(0)
                raw = csv_file.read().decode('latin-1')

            reader  = csv.DictReader(io.StringIO(raw))
            headers = reader.fieldnames or []
            if not headers:
                form.add_error('csv_file', 'Could not detect any column headers in this file.')
                return render(request, 'tracker/csv_import.html', {'form': form})

            preview_rows = []
            for i, row in enumerate(reader):
                if i >= 5:
                    break
                preview_rows.append([row.get(h, '') for h in headers])

            request.session['csv_import'] = {
                'account_id': account.pk,
                'raw':        raw,
                'headers':    headers,
            }
            from .forms import CSVMappingForm
            from .forms import DB_FIELDS
            return render(request, 'tracker/csv_map.html', {
                'mapping_form': CSVMappingForm(headers),
                'headers':      headers,
                'preview_rows': preview_rows,
                'account':      account,
                'db_fields':    DB_FIELDS,
            })
    else:
        form = CSVUploadForm(request.user)

    return render(request, 'tracker/csv_import.html', {'form': form})


@login_required
def csv_import_map(request):
    """Step 2 — map CSV columns to DB fields and execute the import."""
    from .forms import CSVMappingForm, DB_FIELDS, _SKIP_CHOICE

    session_data = request.session.get('csv_import')
    if not session_data:
        messages.warning(request, 'Import session expired — please start again.')
        return redirect('csv_import')

    headers    = session_data['headers']
    raw        = session_data['raw']
    account_id = session_data['account_id']
    account    = get_object_or_404(Account, pk=account_id, user=request.user)

    if request.method == 'POST':
        mapping_form = CSVMappingForm(headers, request.POST)
        if mapping_form.is_valid():
            cd      = mapping_form.cleaned_data

            col_map = {}
            for key, _, _ in DB_FIELDS:
                val = cd.get(f'map_{key}', _SKIP_CHOICE)
                col_map[key] = None if val == _SKIP_CHOICE else val

            reader              = csv.DictReader(io.StringIO(raw))
            created, skipped, errors = 0, 0, []

            for i, row in enumerate(reader, start=2):
                try:
                    raw_amt = row.get(col_map['amount'], '0').strip()
                    raw_amt = raw_amt.replace(',', '').replace('$', '').replace('£', '').replace('€', '')
                    amount  = Decimal(raw_amt)

                    # Derive type from sign: positive = income, negative = expense
                    if amount == 0:
                        errors.append(f'Row {i}: amount is zero — skipped')
                        skipped += 1
                        continue
                    txn_type = 'income' if amount > 0 else 'expense'
                    amount   = abs(amount)

                    date_col    = col_map.get('date')
                    raw_date    = row.get(date_col, '').strip() if date_col else ''
                    parsed_date = _parse_date(raw_date) if raw_date else date.today()
                    if parsed_date is None:
                        errors.append(f'Row {i}: could not parse date "{raw_date}" — skipped')
                        skipped += 1
                        continue

                    desc_col    = col_map.get('description')
                    description = row.get(desc_col, '').strip() if desc_col else ''
                    description = description or 'Imported'

                    category = None
                    cat_col  = col_map.get('category')
                    if cat_col:
                        cat_name = row.get(cat_col, '').strip()
                        if cat_name:
                            category, _ = Category.objects.get_or_create(
                                user=request.user, name=cat_name,
                                defaults={'category_type': 'both'}
                            )

                    notes    = ''
                    note_col = col_map.get('notes')
                    if note_col:
                        notes = row.get(note_col, '').strip()

                    Transaction.objects.create(
                        user=request.user,
                        account=account,
                        transaction_type=txn_type,
                        amount=amount,
                        description=description,
                        date=parsed_date,
                        notes=notes,
                        category=category,
                    )
                    created += 1

                except (InvalidOperation, ValueError) as e:
                    errors.append(f'Row {i}: {e} — skipped')
                    skipped += 1

            del request.session['csv_import']

            # Auto-apply category rules to the newly imported transactions
            if created:
                from .models import apply_category_rules
                rule_hits = apply_category_rules(request.user)
                messages.success(request, f'Imported {created} transaction{"s" if created != 1 else ""}.')
                if rule_hits:
                    messages.success(request, f'Auto-categorised {rule_hits} transaction{"s" if rule_hits != 1 else ""} using your rules.')
            if skipped:
                messages.warning(request, f'{skipped} row{"s" if skipped != 1 else ""} skipped.')
            for err in errors[:8]:
                messages.warning(request, err)

            return redirect('transaction_list')

        # Re-render with errors
        preview_rows = []
        for i, row in enumerate(csv.DictReader(io.StringIO(raw))):
            if i >= 5: break
            preview_rows.append([row.get(h, '') for h in headers])

        return render(request, 'tracker/csv_map.html', {
            'mapping_form': mapping_form,
            'headers':      headers,
            'preview_rows': preview_rows,
            'account':      account,
            'db_fields':    DB_FIELDS,
        })

    return redirect('csv_import')


def _parse_date(raw):
    import re
    from datetime import datetime
    raw = re.split(r'[\sT]', raw.strip())[0]
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%d/%m/%Y','%m-%d-%Y','%d-%m-%Y','%Y/%m/%d','%d.%m.%Y','%m.%d.%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None

# ── Reports ───────────────────────────────────────────────────────────────────

@login_required
def reports(request):
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    txns = Transaction.objects.filter(
        user=request.user, date__gte=month_start, date__lte=month_end
    ).select_related('account', 'category')

    income_total = txns.filter(transaction_type='income').aggregate(t=Sum('amount'))['t'] or 0
    expense_total = txns.filter(transaction_type='expense').aggregate(t=Sum('amount'))['t'] or 0

    # By category
    by_category = txns.filter(transaction_type='expense').values(
        'category__name', 'category__color', 'category__icon'
    ).annotate(total=Sum('amount')).order_by('-total')

    # By account
    by_account = txns.values(
        'account__name', 'account__color', 'account__account_type'
    ).annotate(
        income=Sum('amount', filter=Q(transaction_type='income')),
        expense=Sum('amount', filter=Q(transaction_type='expense')),
    )

    # Month nav
    months = []
    for m in range(1, 13):
        months.append((m, date(year, m, 1).strftime('%B')))

    chart_data = {
        'categories': [c['category__name'] or 'Uncategorized' for c in by_category],
        'amounts': [float(c['total']) for c in by_category],
        'colors': [c['category__color'] or '#6B7280' for c in by_category],
    }

    return render(request, 'tracker/reports.html', {
        'income_total': income_total,
        'expense_total': expense_total,
        'net': income_total - expense_total,
        'by_category': by_category,
        'by_account': by_account,
        'months': months,
        'selected_month': month,
        'selected_year': year,
        'years': range(today.year - 3, today.year + 1),
        'chart_data_json': json.dumps(chart_data),
    })

# ── Category Rules ────────────────────────────────────────────────────────────

@login_required
def rule_list(request):
    from .models import CategoryRule, apply_category_rules
    rules = CategoryRule.objects.filter(user=request.user).select_related('category')

    # Gather a preview: how many transactions each rule would match
    all_txns = Transaction.objects.filter(user=request.user).only('description')
    txn_descriptions = list(all_txns.values_list('description', flat=True))

    rule_stats = []
    for rule in rules:
        count = sum(1 for desc in txn_descriptions if rule.matches(desc))
        rule_stats.append({'rule': rule, 'match_count': count})

    return render(request, 'tracker/rule_list.html', {
        'rule_stats': rule_stats,
        'total_transactions': len(txn_descriptions),
    })


@login_required
def rule_create(request):
    from .forms import CategoryRuleForm
    # Pre-fill keyword if coming from a transaction description link
    initial = {}
    if desc := request.GET.get('description'):
        initial['keyword'] = desc

    if request.method == 'POST':
        form = CategoryRuleForm(request.user, request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.user = request.user
            rule.save()
            messages.success(request, f'Rule created: "{rule.keyword}" → {rule.category}')
            return redirect('rule_list')
    else:
        form = CategoryRuleForm(request.user, initial=initial)
    descriptions = list(
        Transaction.objects.filter(user=request.user)
        .values_list('description', flat=True).distinct()[:500]
    )
    return render(request, 'tracker/rule_form.html', {
        'form': form, 'title': 'Add Rule',
        'descriptions_json': json.dumps(descriptions),
    })


@login_required
def rule_edit(request, pk):
    from .models import CategoryRule
    from .forms import CategoryRuleForm
    rule = get_object_or_404(CategoryRule, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryRuleForm(request.user, request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rule updated.')
            return redirect('rule_list')
    else:
        form = CategoryRuleForm(request.user, instance=rule)
    descriptions = list(
        Transaction.objects.filter(user=request.user)
        .values_list('description', flat=True).distinct()[:500]
    )
    return render(request, 'tracker/rule_form.html', {
        'form': form, 'title': 'Edit Rule', 'rule': rule,
        'descriptions_json': json.dumps(descriptions),
    })


@login_required
def rule_delete(request, pk):
    from .models import CategoryRule
    rule = get_object_or_404(CategoryRule, pk=pk, user=request.user)
    if request.method == 'POST':
        rule.delete()
        messages.success(request, f'Rule "{rule.keyword}" deleted.')
        return redirect('rule_list')
    return render(request, 'tracker/confirm_delete.html', {'obj': rule, 'type': 'Rule'})


@login_required
def rule_apply(request):
    """Apply all active rules to ALL transactions for this user."""
    from .models import apply_category_rules
    if request.method == 'POST':
        updated = apply_category_rules(request.user)
        if updated:
            messages.success(request, f'Done! Updated {updated} transaction{"s" if updated != 1 else ""}.')
        else:
            messages.info(request, 'No transactions needed updating — all already matched.')
    return redirect('rule_list')


@login_required
def rule_export(request):
    """Export all category rules as CSV."""
    from .models import CategoryRule
    rules = CategoryRule.objects.filter(user=request.user).select_related('category')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="category_rules.csv"'

    writer = csv.writer(response)
    writer.writerow(['keyword', 'match_type', 'category', 'min_amount', 'priority', 'is_active'])
    for rule in rules:
        writer.writerow([
            rule.keyword,
            rule.get_match_type_display(),
            rule.category.name,
            rule.min_amount if rule.min_amount else '',
            rule.priority,
            'Yes' if rule.is_active else 'No',
        ])
    return response


@login_required
def rule_import(request):
    """Step 1 — upload rule CSV file."""
    from .forms import RuleCSVUploadForm
    if request.method == 'POST':
        form = RuleCSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            try:
                raw = csv_file.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                csv_file.seek(0)
                raw = csv_file.read().decode('latin-1')

            reader = csv.DictReader(io.StringIO(raw))
            headers = reader.fieldnames or []
            if not headers:
                form.add_error('csv_file', 'Could not detect any column headers in this file.')
                return render(request, 'tracker/rule_import.html', {'form': form})

            preview_rows = []
            for i, row in enumerate(reader):
                if i >= 5:
                    break
                preview_rows.append([row.get(h, '') for h in headers])

            request.session['rule_import'] = {
                'raw': raw,
                'headers': headers,
            }
            from .forms import RuleCSVMappingForm, RULE_IMPORT_FIELDS
            return render(request, 'tracker/rule_import_map.html', {
                'mapping_form': RuleCSVMappingForm(headers),
                'headers': headers,
                'preview_rows': preview_rows,
                'rule_import_fields': RULE_IMPORT_FIELDS,
            })
    else:
        form = RuleCSVUploadForm()

    return render(request, 'tracker/rule_import.html', {'form': form})


@login_required
def rule_import_map(request):
    """Step 2 — map CSV columns to rule fields and execute the import."""
    from .forms import RuleCSVMappingForm, RULE_IMPORT_FIELDS, _RULE_SKIP_CHOICE
    from .models import CategoryRule

    session_data = request.session.get('rule_import')
    if not session_data:
        messages.warning(request, 'Import session expired — please start again.')
        return redirect('rule_import')

    headers = session_data['headers']
    raw = session_data['raw']

    if request.method == 'POST':
        mapping_form = RuleCSVMappingForm(headers, request.POST)
        if mapping_form.is_valid():
            cd = mapping_form.cleaned_data

            col_map = {}
            for key, _, _ in RULE_IMPORT_FIELDS:
                val = cd.get(f'map_{key}', _RULE_SKIP_CHOICE)
                col_map[key] = None if val == _RULE_SKIP_CHOICE else val

            reader = csv.DictReader(io.StringIO(raw))
            created, skipped, errors = 0, 0, []

            for i, row in enumerate(reader, start=2):
                try:
                    # Extract required fields
                    keyword = row.get(col_map['keyword'], '').strip() if col_map['keyword'] else ''
                    if not keyword:
                        skipped += 1
                        errors.append(f'Row {i}: Missing keyword')
                        continue

                    category_name = row.get(col_map['category'], '').strip() if col_map['category'] else ''
                    if not category_name:
                        skipped += 1
                        errors.append(f'Row {i}: Missing category')
                        continue

                    # Try to find the category
                    try:
                        category = Category.objects.get(user=request.user, name=category_name)
                    except Category.DoesNotExist:
                        skipped += 1
                        errors.append(f'Row {i}: Category "{category_name}" not found')
                        continue

                    # Extract optional fields
                    match_type = 'contains'
                    if col_map['match_type']:
                        match_type_val = row.get(col_map['match_type'], 'contains').strip().lower()
                        valid_types = ['contains', 'exact', 'startswith', 'endswith', 'regex']
                        if match_type_val in valid_types:
                            match_type = match_type_val

                    min_amount = None
                    if col_map['min_amount']:
                        min_amt_str = row.get(col_map['min_amount'], '').strip()
                        if min_amt_str:
                            try:
                                min_amount = Decimal(min_amt_str)
                            except (InvalidOperation, ValueError):
                                pass

                    priority = 10
                    if col_map['priority']:
                        priority_str = row.get(col_map['priority'], '10').strip()
                        try:
                            priority = int(priority_str)
                        except ValueError:
                            pass

                    # Create or update the rule
                    rule, created_flag = CategoryRule.objects.get_or_create(
                        user=request.user,
                        keyword=keyword,
                        match_type=match_type,
                        defaults={
                            'category': category,
                            'min_amount': min_amount,
                            'priority': priority,
                            'is_active': True,
                        }
                    )
                    if created_flag:
                        created += 1
                    else:
                        skipped += 1
                        errors.append(f'Row {i}: Rule "{keyword}" already exists')

                except Exception as e:
                    skipped += 1
                    errors.append(f'Row {i}: {str(e)}')

            # Show summary
            messages.success(request, f'Import complete: {created} created, {skipped} skipped.')
            if errors and len(errors) <= 10:
                for err in errors:
                    messages.warning(request, err)
            elif errors:
                messages.warning(request, f'{len(errors)} errors — see log for details.')

            del request.session['rule_import']
            return redirect('rule_list')
    else:
        mapping_form = RuleCSVMappingForm(headers)

    from .forms import RULE_IMPORT_FIELDS
    return render(request, 'tracker/rule_import_map.html', {
        'mapping_form': mapping_form,
        'headers': headers,
        'rule_import_fields': RULE_IMPORT_FIELDS,
    })

# ── Budgets ───────────────────────────────────────────────────────────────────

@login_required
def budget_list(request):
    from .models import Budget, Transaction
    from django.db.models import Sum, Q
    from datetime import date

    budgets = Budget.objects.filter(user=request.user).select_related('category')

    today = date.today()
    month_start = today.replace(day=1)

    # Annotate each budget with current-month actuals
    budget_rows = []
    for b in budgets:
        txn_type = 'income' if b.category.category_type == 'income' else 'expense'
        actual = Transaction.objects.filter(
            user=request.user,
            category=b.category,
            transaction_type=txn_type,
            date__gte=month_start,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        pct = int(actual / b.amount * 100) if b.amount else 0
        budget_rows.append({
            'budget':   b,
            'actual':   actual,
            'pct':      min(pct, 100),
            'over':     actual > b.amount,
            'txn_type': txn_type,
        })

    return render(request, 'tracker/budget_list.html', {
        'budget_rows': budget_rows,
        'month_label': today.strftime('%B %Y'),
    })


@login_required
def budget_create(request):
    from .forms import BudgetForm
    if request.method == 'POST':
        form = BudgetForm(request.user, request.POST)
        if form.is_valid():
            b = form.save(commit=False)
            b.user = request.user
            b.save()
            messages.success(request, f'Budget created for {b.category}.')
            return redirect('budget_list')
    else:
        form = BudgetForm(request.user)
    return render(request, 'tracker/budget_form.html', {'form': form, 'title': 'Add Budget'})


@login_required
def budget_edit(request, pk):
    from .models import Budget
    from .forms import BudgetForm
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.user, request.POST, instance=budget)
        if form.is_valid():
            form.save()
            messages.success(request, 'Budget updated.')
            return redirect('budget_list')
    else:
        form = BudgetForm(request.user, instance=budget)
    return render(request, 'tracker/budget_form.html', {
        'form': form, 'title': 'Edit Budget', 'budget': budget
    })


@login_required
def budget_delete(request, pk):
    from .models import Budget
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        budget.delete()
        messages.success(request, 'Budget deleted.')
        return redirect('budget_list')
    return render(request, 'tracker/confirm_delete.html', {'obj': budget, 'type': 'Budget'})


# ── Forecast ──────────────────────────────────────────────────────────────────

@login_required
def forecast(request):
    from .forecast import build_forecast

    try:
        months_ahead = int(request.GET.get('months', 6))
        months_ahead = max(1, min(months_ahead, 24))
    except (ValueError, TypeError):
        months_ahead = 6

    forecast_months = build_forecast(request.user, months_ahead=months_ahead)

    # Build chart data — projected income/expense/net per month + running balance
    chart_labels   = [fm.label for fm in forecast_months]
    chart_income   = [float(fm.projected_income)  for fm in forecast_months]
    chart_expense  = [float(fm.projected_expense) for fm in forecast_months]
    chart_net      = [float(fm.projected_net)     for fm in forecast_months]
    chart_balance  = [float(fm.running_balance)   for fm in forecast_months]

    return render(request, 'tracker/forecast.html', {
        'forecast_months': forecast_months,
        'months_ahead':    months_ahead,
        'chart_data_json': json.dumps({
            'labels':  chart_labels,
            'income':  chart_income,
            'expense': chart_expense,
            'net':     chart_net,
            'balance': chart_balance,
        }),
        'has_data': bool(forecast_months and any(
            fm.projected_income or fm.projected_expense for fm in forecast_months
        )),
    })
