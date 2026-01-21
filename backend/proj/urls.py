from django.contrib import admin, include
from django.urls import path
# Importujemy widoki z pliku, który stworzyłaś wyżej (np. z folderu api)
from api.views import chart_data_eurpln, chart_data_plneur, history_rates

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('rates.urls')),
    # --- Nowe Endpointy dla Reacta ---
    path('api/chart-data/eurpln/', chart_data_eurpln, name='chart_eur'),
    path('api/chart-data/plneur/', chart_data_plneur, name='chart_pln'),
    path('api/rates/history/', history_rates, name='history_all'),
]