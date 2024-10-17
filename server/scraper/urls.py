from django.urls import path
from .views import fetch_team_rankings

urlpatterns = [
    path('rankings/', fetch_team_rankings, name='fetch_team_rankings'),
]
