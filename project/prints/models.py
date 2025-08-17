# prints/models.py
from django.db import models
from django.contrib.auth.models import User

class ChatSession(models.Model):
    """채팅 세션"""
    session_id = models.CharField(max_length=100, primary_key=True, verbose_name="세션 ID")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="사용자")
    
    # 채팅 데이터
    history = models.JSONField(default=list, verbose_name="대화 기록")
    slots = models.JSONField(default=dict, verbose_name="슬롯 데이터")
    
    # 상태
    is_active = models.BooleanField(default=True, verbose_name="활성화")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="시작일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="마지막 활동")
    
    class Meta:
        db_table = 'chat_sessions'
        verbose_name = '채팅 세션'
        verbose_name_plural = '채팅 세션'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"세션 {self.session_id} - {self.updated_at.strftime('%Y-%m-%d %H:%M')}"
