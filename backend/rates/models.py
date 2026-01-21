from django.db import models

class HistoricalCurrency(models.Model):
    date = models.DateTimeField(primary_key=True)
    eurpln = models.DecimalField(max_digits=18, decimal_places=8, null=True)
    usdpln = models.DecimalField(max_digits=18, decimal_places=8, null=True)

    class Meta:
        db_table = 'historical_currency'
        managed = False
