from django.contrib import admin
from .models import Patient, Doctor, Prescription, Pharmacy, Laboratory

admin.site.register(Patient)
admin.site.register(Doctor)

admin.site.register(Prescription)
admin.site.register(Pharmacy)
admin.site.register(Laboratory)

