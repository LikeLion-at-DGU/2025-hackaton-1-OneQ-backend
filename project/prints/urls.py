from django.urls import path
from .views import chat, reset_chat

urlpatterns = [
    # AI 채팅 견적 API
    path("chat/", chat, name="chat"),
    path("reset/", reset_chat, name="reset_chat"),
]
