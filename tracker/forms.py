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
