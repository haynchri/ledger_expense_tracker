from django import forms
from .models import Account, Category, Statement, Transaction


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


class CategoryCSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.csv'}),
        help_text='Upload a category CSV file to map its columns.'
    )


CATEGORY_IMPORT_FIELDS = [
    ('name', 'Name', True),
    ('category_type', 'Type', False),
    ('icon', 'Icon', False),
    ('color', 'Color', False),
]


_CATEGORY_SKIP_CHOICE = '__skip__'


class CategoryCSVMappingForm(forms.Form):
    def __init__(self, csv_headers, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(_CATEGORY_SKIP_CHOICE, '— skip / not in file —')] + [
            (header, header) for header in csv_headers
        ]
        auto_candidates = {
            'name': ['name', 'category', 'category name', 'label'],
            'category_type': ['category_type', 'category type', 'type'],
            'icon': ['icon', 'emoji', 'symbol'],
            'color': ['color', 'colour', 'hex'],
        }
        lower_map = {header.lower(): header for header in csv_headers}

        for key, label, _ in CATEGORY_IMPORT_FIELDS:
            initial = _CATEGORY_SKIP_CHOICE
            for candidate in auto_candidates[key]:
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
        name_column = cleaned.get('map_name', _CATEGORY_SKIP_CHOICE)
        if not name_column or name_column == _CATEGORY_SKIP_CHOICE:
            self.add_error('map_name', 'Required — please map this to a column.')
        return cleaned


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'account', 'category', 'statement', 'amount', 'description', 'date', 'notes', 'receipt', 'recurring_period']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-input'}),
            'account': forms.Select(attrs={'class': 'form-input'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'statement': forms.Select(attrs={'class': 'form-input'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'min': '0.01'}),
            'description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'What was this for?'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional notes...'}),
            'receipt': forms.FileInput(attrs={'class': 'form-input'}),
            'recurring_period': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(user=user, is_active=True)
        self.fields['category'].queryset = Category.objects.filter(user=user)
        self.fields['statement'].queryset = Statement.objects.filter(user=user).select_related('account')
        self.fields['statement'].label_from_instance = (
            lambda statement: statement.description or str(statement)
        )
        self.fields['category'].required = False
        self.fields['statement'].required = False


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
    category = forms.ChoiceField(
        required=False, choices=[],
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
        
        # Build category choices: all categories + uncategorized option
        category_choices = [('', 'All Categories')]
        for cat in Category.objects.filter(user=user).order_by('name'):
            category_choices.append((str(cat.id), str(cat)))
        category_choices.append(('__uncategorized__', 'Uncategorized'))
        self.fields['category'].choices = category_choices


class CSVUploadForm(forms.Form):
    """Step 1 — pick account + upload file + optional statement date."""
    account = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-input'}),
        help_text='Which account should these transactions be assigned to?'
    )
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.csv'}),
        help_text='Upload any CSV — you will map columns on the next screen.'
    )
    statement_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        help_text='Optional — set the statement date to associate with all imported transactions'
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


class RuleCSVUploadForm(forms.Form):
    """Step 1 — upload rule CSV file."""
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': '.csv'}),
        help_text='Upload any CSV — you will map columns on the next screen.'
    )


# Rule import fields: (key, label, required)
RULE_IMPORT_FIELDS = [
    ('keyword',    'Keyword',    True),
    ('match_type', 'Match Type', False),  # optional, defaults to 'contains'
    ('category',   'Category',   True),
    ('min_amount', 'Min Amount', False),
    ('priority',   'Priority',   False),  # optional, defaults to 10
]

_RULE_SKIP_CHOICE = '__skip__'


class RuleCSVMappingForm(forms.Form):
    """Step 2 — map each rule field to a CSV column header."""

    def __init__(self, csv_headers, *args, **kwargs):
        super().__init__(*args, **kwargs)
        skip_choices = [(_RULE_SKIP_CHOICE, '— skip / not in file —')]
        choices = skip_choices + [(h, h) for h in csv_headers]

        lower_map = {h.lower(): h for h in csv_headers}
        auto_candidates = {
            'keyword':    ['keyword', 'pattern', 'search', 'text'],
            'match_type': ['match_type', 'match type', 'type', 'match'],
            'category':   ['category', 'cat', 'assigns to'],
            'min_amount': ['min_amount', 'min amount', 'min', 'minimum'],
            'priority':   ['priority', 'order', 'rank', 'sequence'],
        }

        for key, label, _ in RULE_IMPORT_FIELDS:
            initial = _RULE_SKIP_CHOICE
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
        for key, _, required in RULE_IMPORT_FIELDS:
            val = cleaned.get(f'map_{key}', _RULE_SKIP_CHOICE)
            if required and (not val or val == _RULE_SKIP_CHOICE):
                self.add_error(f'map_{key}', 'Required — please map this to a column.')
        return cleaned


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
