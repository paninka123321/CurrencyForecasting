from django.http import JsonResponse
from django.db import connection
import datetime

def dictfetchall(cursor):
    """Pomocnicza funkcja: zamienia wyniki SQL na słowniki (JSON-friendly)"""
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

def get_combined_chart_data(request, direction):
    """
    Uniwersalna funkcja dla obu kierunków (EURPLN i PLNEUR).
    direction: 'eur' lub 'pln'
    """
    # 1. Ustalamy nazwy tabel i kolumn w zależności od kierunku
    if direction == 'eur':
        pred_table = 'predictions_eurpln'
        hist_col = 'eurpln'
        pair_name = 'EURPLN'
    else:
        pred_table = 'predictions_plneur'
        hist_col = '1/eurpln' # Wyliczamy odwrotność w locie
        pair_name = 'PLNEUR'

    with connection.cursor() as cursor:
        # A. POBIERANIE HISTORII (Ostatnie 3 dni - linia ciągła)
        # Pobieramy co 15 minut, żeby nie zamulić wykresu tysiącami punktów
        # lub co 1 minutę, jeśli chcesz super dokładność (zmieniam na 1m dla spójności)
        sql_hist = f"""
            SELECT date, {hist_col} as value, 'history' as type, NULL as model_name
            FROM historical_currency 
            WHERE date > NOW() - INTERVAL '3 days'
            ORDER BY date ASC
        """
        cursor.execute(sql_hist)
        history_data = dictfetchall(cursor)

        # B. POBIERANIE PREDYKCJI (Przyszłość/Teraźniejszość - linia predykcji)
        # Bierzemy dane z tabeli predykcji, które są "świeże" (np. też z ostatnich 3 dni + przyszłość)
        sql_pred = f"""
            SELECT target_date as date, predicted_rate as value, 'prediction' as type, model_name
            FROM {pred_table}
            WHERE target_date > NOW() - INTERVAL '3 days'
            ORDER BY target_date ASC
        """
        cursor.execute(sql_pred)
        prediction_data = dictfetchall(cursor)
        
        # C. POBIERANIE METRYK (Ostatni trening dla danej pary)
        # Pobieramy wszystkie modele z ostatniego treningu
        sql_metrics = """
            SELECT selected_model as model_name, mae, r2, trained_at
            FROM model_metrics
            WHERE pair = %s
            AND trained_at = (SELECT MAX(trained_at) FROM model_metrics WHERE pair = %s)
            ORDER BY mae ASC
        """
        cursor.execute(sql_metrics, [pair_name, pair_name])
        metrics_data = dictfetchall(cursor)

    # Łączymy dane do wykresu i sortujemy
    combined_chart = history_data + prediction_data
    # Sortowanie po dacie (w Pythonie, bo łączymy dwie różne tabele)
    combined_chart.sort(key=lambda x: x['date'])

    return JsonResponse({
        "chart_data": combined_chart,
        "metrics": metrics_data
    })

# --- KONKRETNE WIDOKI DLA URLi ---

def chart_data_eurpln(request):
    return get_combined_chart_data(request, direction='eur')

def chart_data_plneur(request):
    return get_combined_chart_data(request, direction='pln')

def history_rates(request):
    """Zwraca długą historię (np. rok) dla dolnego, zielonego wykresu"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT date, eurpln, 1/eurpln as plneur 
            FROM historical_currency 
            ORDER BY date ASC
        """)
        data = dictfetchall(cursor)
    return JsonResponse(data, safe=False)