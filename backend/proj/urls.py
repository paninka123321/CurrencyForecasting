from django.urls import path, include
# Importujemy widoki z pliku, który stworzyłaś wyżej (np. z folderu api)
from api.views import chart_data_eurpln, chart_data_plneur, history_rates, advanced_prediction_view

urlpatterns = [
    path('api/', include('rates.urls')),
    # --- Nowe Endpointy dla Reacta ---
    path('api/chart-data/eurpln/', chart_data_eurpln, name='chart_eur'),
    path('api/advanced-prediction/', advanced_prediction_view, name='chart_adv'),
    path('api/chart-data/plneur/', chart_data_plneur, name='chart_pln'),
    path('api/rates/history/', history_rates, name='history_all'),
]