from django.urls import path
from .views import list_rates

urlpatterns = [
    path('rates/', list_rates),
]
