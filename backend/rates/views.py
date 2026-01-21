from django.http import JsonResponse
from .models import HistoricalCurrency
from django.forms.models import model_to_dict

def list_rates(request):
    qs = HistoricalCurrency.objects.order_by('-date')[:500]
    data = [model_to_dict(x) for x in qs]
    return JsonResponse(data, safe=False)
