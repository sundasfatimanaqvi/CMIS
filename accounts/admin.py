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


from .models import AccessLog, ConsentGrant  # noqa: E402


@admin.register(ConsentGrant)
class ConsentGrantAdmin(admin.ModelAdmin):
    list_display = ('patient', 'grantee', 'scope', 'source', 'created_at', 'expires_at', 'revoked_at')
    list_filter = ('scope', 'source')


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'actor_role', 'patient', 'scope', 'action', 'allowed', 'basis')
    list_filter = ('allowed', 'basis', 'actor_role')

    # Audit rows must not be edited or deleted from the admin.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
