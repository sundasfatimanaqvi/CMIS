from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('credits/', views.credits, name='credits'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect_view, name='dashboard'),

    # Patient
    path('patient_dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('search-doctor/', views.search_doctor, name='search_doctor'),
    path('doctors/<int:doctor_id>/book/', views.book_appointment, name='book_appointment'),
    path('doctors/<int:doctor_id>/slots/', views.doctor_slots, name='doctor_slots'),
    path('api/chatbot-conversation/', views.chatbot_conversation, name='chatbot_conversation'),
    path('appointments/<int:appointment_id>/update/', views.update_appointment, name='update_appointment'),

    path('sharing/', views.sharing_access, name='sharing_access'),
    path('sharing/grant/', views.consent_grant, name='consent_grant'),
    path('sharing/revoke/<int:grant_id>/', views.consent_revoke, name='consent_revoke'),

    # Doctor
    path('doctor_dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/profile/', views.doctor_profile, name='doctor_profile'),
    path('search_patient/', views.search_patient, name='search_patient'),
    path('patient_management/<str:patient_id>/', views.patient_management, name='patient_management'),
    path('prescribe_medicine/<str:patient_id>/', views.prescribe_medicine, name='prescribe_medicine'),
    path('prescribe_test/<str:patient_id>/', views.prescribe_test, name='prescribe_test'),
    path('add_medical_history/<str:patient_id>/', views.add_medical_history, name='add_medical_history'),
    path('medical_history/<str:patient_id>/', views.view_medical_history, name='medical_history'),
    path('break_glass/<str:patient_id>/', views.break_glass, name='break_glass'),

    # Pharmacy
    path('pharmacy/', views.pharmacy_dashboard, name='pharmacy_dashboard'),
    path('pharmacy/lookup/', views.pharmacy_lookup, name='pharmacy_lookup'),
    path('pharmacy/toggle/<int:prescription_id>/', views.toggle_prescription_status, name='toggle_prescription_status'),

    # Laboratory
    path('laboratory/', views.laboratory_dashboard, name='laboratory_dashboard'),
    path('laboratory/toggle/<int:test_id>/', views.toggle_test_status, name='toggle_test_status'),
]
