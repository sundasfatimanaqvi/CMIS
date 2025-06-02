from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('patient_dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path("search-doctor/", views.search_doctor, name="search_doctor"),

    path('doctor_dashboard/', views.doctor_dashboard, name='doctor_dashboard'),

    path('search_patient/', views.search_patient, name='search_patient'),
    path('patient_management/<str:patient_id>/', views.patient_management, name='patient_management'),
    path("doctor/profile/", views.doctor_profile, name="doctor_profile"),
    path("prescribe_medicine/<str:patient_id>/", views.prescribe_medicine, name="prescribe_medicine"),
    path('prescribe_test/<str:patient_id>/', views.prescribe_test, name='prescribe_test'),
    path('add_medical_history/<str:patient_id>/', views.add_medical_history, name='add_medical_history'),



    
    
    path('pharmacy/', views.pharmacy_dashboard, name='pharmacy_dashboard'),
    path('pharmacy/lookup/', views.pharmacy_lookup, name='pharmacy_lookup'),
    path('pharmacy/toggle/<int:prescription_id>/', views.toggle_prescription_status, name='toggle_prescription_status'),
]
