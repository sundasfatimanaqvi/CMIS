from django.contrib import admin
from .models import (
    Patient, Doctor, Prescription, Pharmacy, Laboratory,
    MedicalTest, MedicalHistory, Appointment,
)

admin.site.register(Patient)
admin.site.register(Doctor)
admin.site.register(Prescription)
admin.site.register(Pharmacy)
admin.site.register(Laboratory)
admin.site.register(MedicalTest)
admin.site.register(MedicalHistory)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'date', 'time', 'status')
    list_filter = ('status', 'date')
