from django.contrib import admin
from .models import Account, Category, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_type', 'balance', 'user', 'is_active']
    list_filter = ['account_type', 'is_active']
    search_fields = ['name', 'user__username']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'icon', 'user']
    list_filter = ['category_type']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['description', 'amount', 'transaction_type', 'account', 'category', 'date', 'user']
    list_filter = ['transaction_type', 'date']
    search_fields = ['description', 'user__username']

from .models import CategoryRule

@admin.register(CategoryRule)
class CategoryRuleAdmin(admin.ModelAdmin):
    list_display = ['keyword', 'match_type', 'category', 'priority', 'is_active', 'user']
    list_filter  = ['match_type', 'is_active']
    search_fields = ['keyword']

from .models import Budget

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['category', 'amount', 'user']
    search_fields = ['category__name']
