from django.urls import path
from .views import ai_test

urlpatterns = [
    path("ai-test", ai_test),
]
