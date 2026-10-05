from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('wallet/', views.get_wallet_status, name='wallet_status'),
    path('topup/', views.topup_wallet, name='topup_wallet'),
    path('transactions/', views.list_transactions, name='list_transactions'),
]
