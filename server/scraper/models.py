from django.db import models

class Team(models.Model):
    name = models.CharField(max_length=100)
    offensive_stats = models.JSONField()
    defensive_stats = models.JSONField()
    ranking = models.IntegerField()

    def __str__(self):
        return self.name
