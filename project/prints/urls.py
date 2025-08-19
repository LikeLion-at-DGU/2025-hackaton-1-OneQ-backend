from django.urls import path
from . import views

urlpatterns = [
    # === 인쇄소 등록 (단계별) ===
    path('printshops/create-step1/', views.printshop_create_step1, name='printshop_create_step1'),
    path('printshops/<int:pk>/update-step2/', views.printshop_update_step2, name='printshop_update_step2'),
    path('printshops/<int:pk>/finalize/', views.printshop_finalize, name='printshop_finalize'),
    path('printshops/<int:pk>/registration-status/', views.printshop_registration_status, name='printshop_registration_status'),
    
    # === 인쇄소 등록 (한 번에) ===
    path('printshops/create/', views.printshop_create, name='printshop_create'),
    
    # === 인쇄소 관리 ===
    path('printshops/', views.printshop_list, name='printshop_list'),
    path('printshops/search/', views.printshop_search, name='printshop_search'),
    path('printshops/<int:pk>/', views.printshop_detail, name='printshop_detail'),
    path('printshops/<int:pk>/update/', views.printshop_update, name='printshop_update'),
    path('printshops/<int:pk>/verify-password/', views.printshop_verify_password, name='printshop_verify_password'),
    
    # === 인쇄소 인증 (관리자용) ===
    path('printshops/<int:pk>/verify/', views.printshop_verify, name='printshop_verify'),
    path('printshops/<int:pk>/verification-status/', views.printshop_verification_status, name='printshop_verification_status'),
    
    # === 채팅 세션 ===
    path('chat/sessions/', views.chatsession_create, name='chatsession_create'),
    path('chat/sessions/<str:session_id>/send/', views.chatsession_send_message, name='chatsession_send_message'),
]
