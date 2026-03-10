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

    total_income = qs.filter(transaction_type='income').aggregate(t=Sum('amount'))['t'] or 0
    total_expense = qs.filter(transaction_type='expense').aggregate(t=Sum('amount'))['t'] or 0

    return render(request, 'tracker/transaction_list.html', {
        'transactions': qs,
        'filter_form': filter_form,
        'total_income': total_income,
        'total_expense': total_expense,
        'net': total_income - total_expense,
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

            if created:
                messages.success(request, f'Imported {created} transaction{"s" if created != 1 else ""}.')
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
