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
