from django import forms
from .models import Account, Category, Transaction


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'account_type', 'balance', 'credit_limit', 'last_four', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Chase Checking'}),
            'account_type': forms.Select(attrs={'class': 'form-input'}),
            'balance': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'credit_limit': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'last_four': forms.TextInput(attrs={'class': 'form-input', 'maxlength': '4', 'placeholder': '1234'}),
            'color': forms.TextInput(attrs={'class': 'form-input', 'type': 'color'}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'category_type', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Groceries'}),
            'category_type': forms.Select(attrs={'class': 'form-input'}),
            'icon': forms.Select(attrs={'class': 'form-input'},
                                 choices=Category.ICONS),
            'color': forms.TextInput(attrs={'class': 'form-input', 'type': 'color'}),
        }


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'account', 'category', 'amount', 'description', 'date', 'notes', 'receipt', 'is_recurring']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-input'}),
            'account': forms.Select(attrs={'class': 'form-input'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'min': '0.01'}),
            'description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'What was this for?'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional notes...'}),
            'receipt': forms.FileInput(attrs={'class': 'form-input'}),
            'is_recurring': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user, is_active=True)
        self.fields['category'].queryset = Category.objects.filter(user=user)
        self.fields['category'].required = False


class TransactionFilterForm(forms.Form):
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
    ]

    account = forms.ModelChoiceField(
        queryset=None, required=False, empty_label='All Accounts',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    category = forms.ModelChoiceField(
        queryset=None, required=False, empty_label='All Categories',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    transaction_type = forms.ChoiceField(
        choices=[('', 'All Types'), ('income', 'Income'), ('expense', 'Expense')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Search descriptions...'})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user, is_active=True)
        self.fields['category'].queryset = Category.objects.filter(user=user)


class CSVImportForm(forms.Form):
    account = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-input'}),
        help_text='Which account should these transactions be assigned to?'
    )
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.csv'}),
        help_text='CSV must have columns: date, description, amount, type (income/expense), category (optional)'
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user, is_active=True)


class CSVUploadForm(forms.Form):
    """Step 1 — pick account + upload file."""
    account = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-input'}),
        help_text='Which account should these transactions be assigned to?'
    )
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.csv'}),
        help_text='Upload any CSV — you will map columns on the next screen.'
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user, is_active=True)


# DB fields we need to map to: (key, label, required)
# transaction_type is intentionally excluded — it is derived from amount sign.
DB_FIELDS = [
    ('date',        'Date',        True),
    ('description', 'Description', True),
    ('amount',      'Amount',      True),
    ('category',    'Category',    False),
    ('notes',       'Notes',       False),
]

_SKIP_CHOICE = '__skip__'


class CSVMappingForm(forms.Form):
    """Step 2 — map each DB field to a CSV column header.
    Transaction type is determined automatically from the amount sign:
    positive → income, negative → expense.
    """

    def __init__(self, csv_headers, *args, **kwargs):
        super().__init__(*args, **kwargs)
        skip_choices = [(_SKIP_CHOICE, '— skip / not in file —')]
        choices = skip_choices + [(h, h) for h in csv_headers]

        lower_map = {h.lower(): h for h in csv_headers}
        auto_candidates = {
            'date':        ['date', 'trans date', 'transaction date', 'posted date', 'post date'],
            'description': ['description', 'desc', 'memo', 'narrative', 'details', 'payee', 'merchant'],
            'amount':      ['amount', 'amt', 'debit', 'credit', 'value', 'transaction amount'],
            'category':    ['category', 'cat', 'label', 'tag'],
            'notes':       ['notes', 'note', 'comment', 'comments', 'reference', 'ref'],
        }

        for key, label, _ in DB_FIELDS:
            initial = _SKIP_CHOICE
            for candidate in auto_candidates.get(key, []):
                if candidate in lower_map:
                    initial = lower_map[candidate]
                    break
            self.fields[f'map_{key}'] = forms.ChoiceField(
                choices=choices,
                required=False,
                label=label,
                initial=initial,
                widget=forms.Select(attrs={'class': 'form-input'}),
            )

    def clean(self):
        cleaned = super().clean()
        for key, _, required in DB_FIELDS:
            val = cleaned.get(f'map_{key}', _SKIP_CHOICE)
            if required and (not val or val == _SKIP_CHOICE):
                self.add_error(f'map_{key}', 'Required — please map this to a column.')
        return cleaned


class CategoryRuleForm(forms.ModelForm):
    class Meta:
        from .models import CategoryRule
        model  = CategoryRule
        fields = ['keyword', 'match_type', 'category', 'min_amount', 'priority', 'is_active']
        widgets = {
            'keyword':    forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g. AMAZON, Netflix, Whole Foods'
            }),
            'match_type': forms.Select(attrs={'class': 'form-input'}),
            'category':   forms.Select(attrs={'class': 'form-input'}),
            'min_amount': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01', 'min': '0',
                'placeholder': 'e.g. 10.00 (leave blank to match any amount)',
            }),
            'priority':   forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'is_active':  forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(user=user)


class BudgetForm(forms.ModelForm):
    class Meta:
        from .models import Budget
        model  = Budget
        fields = ['category', 'amount', 'notes']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-input'}),
            'amount':   forms.NumberInput(attrs={
                'class': 'form-input', 'step': '0.01', 'min': '0.01',
                'placeholder': 'Monthly target, e.g. 500.00',
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Optional note about this budget',
            }),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(user=user)
