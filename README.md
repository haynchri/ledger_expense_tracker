# Ledger — Django Expense Tracker

A full-featured personal finance tracker built with Django. Track income and
expenses across Checking, Savings, and Credit Card accounts with categories,
charts, CSV import/export, and monthly reports.

## Features

- **Accounts** — Checking, Savings, Credit Card with balance tracking and credit utilization
- **Transactions** — Link every debit/receipt to a specific account; attach receipt files
- **Categories** — Color-coded, emoji tags for spending (10 defaults auto-created on signup)
- **Dashboard** — Monthly income/expense summary, 6-month bar chart, top spending by category
- **Reports** — Monthly doughnut chart breakdown by category and per-account activity
- **CSV Import** — Bulk import transactions from a CSV file to any account
- **CSV Export** — Export filtered transactions to CSV
- **Multi-user** — Each user's data is fully isolated

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run migrations

```bash
python manage.py migrate
```

### 3. Create a superuser (optional, for /admin)

```bash
python manage.py createsuperuser
```

### 4. Start the development server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000** — you'll be redirected to login.
Register a new account at `/register/` to get started.

---

## CSV Import Format

Your CSV must have a header row with these columns:

```
date,type,category,description,amount,notes
2024-01-15,expense,Food & Dining,Grocery run,85.50,Weekly shop
2024-01-16,income,Salary,Paycheck,3000.00,
```

| Column | Required | Format |
|--------|----------|--------|
| date | ✅ | YYYY-MM-DD |
| type | ✅ | `income` or `expense` |
| description | ✅ | Any text |
| amount | ✅ | Positive number |
| category | ❌ | Must match an existing category name (or will be created) |
| notes | ❌ | Any text |

---

## Project Structure

```
expense_tracker/
├── manage.py
├── requirements.txt
├── expense_tracker/        # Django project config
│   ├── settings.py
│   └── urls.py
└── tracker/                # Main app
    ├── models.py           # Account, Category, Transaction
    ├── views.py            # All views
    ├── forms.py            # All forms
    ├── urls.py             # App URL routing
    ├── admin.py            # Django admin registration
    ├── templatetags/
    │   └── tracker_extras.py
    └── templates/tracker/  # All HTML templates
        ├── base.html
        ├── dashboard.html
        ├── transaction_*.html
        ├── account_*.html
        ├── category_*.html
        ├── reports.html
        └── csv_import.html
```

---

## Production Notes

- Change `SECRET_KEY` in `settings.py` to a secure random value (use env variable)
- Set `DEBUG = False` in production
- Configure `ALLOWED_HOSTS` with your domain
- Add `MEDIA_ROOT` / `MEDIA_URL` settings to serve uploaded receipt files
- Consider PostgreSQL instead of SQLite for production
