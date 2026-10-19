from django.urls import path

from .views import HealthView, PlanTripView

urlpatterns = [
    path("plan-trip/", PlanTripView.as_view(), name="plan-trip"),
    path("health/", HealthView.as_view(), name="health"),
]
