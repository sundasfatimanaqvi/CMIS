import uuid
from django.db import models
from django.contrib.auth.models import User
import datetime
from django.templatetags.static import static


def generate_unique_id():
    # Generates a unique 8-character ID
    return str(uuid.uuid4())[:8]

class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient')
    patient_id = models.CharField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.patient_id:
            self.patient_id = generate_unique_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - Patient"

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor')
    doctor_id = models.CharField(max_length=100, unique=True, blank=True)
    profile_picture = models.ImageField(upload_to='doctor_profiles/', default='doctor_profiles/default-avatar.png', blank=True)
    specialization = models.CharField(max_length=100, blank=True, default='General Physician')
    working_hours_start = models.TimeField(default=datetime.time(9, 0))
    working_hours_end = models.TimeField(default=datetime.time(17, 0))
    # Comma separated ISO dates (YYYY-MM-DD) on which the doctor is not available
    unavailable_days = models.TextField(blank=True, default='')

    def save(self, *args, **kwargs):
        if not self.doctor_id:
            self.doctor_id = generate_unique_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - Doctor"

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def availability(self):
        return f"{self.working_hours_start:%H:%M} - {self.working_hours_end:%H:%M}"

    @property
    def avatar_url(self):
        name = self.profile_picture.name if self.profile_picture else ''
        if name and 'default-avatar' not in name:
            return self.profile_picture.url
        # Friendly illustrated fallback (cycles through the bundled doctor pictures)
        return static(f"doctors/doctor{(self.pk or 0) % 3 + 1}.png")

    def unavailable_date_set(self):
        days = set()
        for chunk in self.unavailable_days.split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                days.add(datetime.date.fromisoformat(chunk))
            except ValueError:
                continue
        return days

    def time_slots(self, minutes=30):
        """All appointment start times for one working day."""
        slots = []
        current = datetime.datetime.combine(datetime.date.today(), self.working_hours_start)
        end = datetime.datetime.combine(datetime.date.today(), self.working_hours_end)
        step = datetime.timedelta(minutes=minutes)
        while current + step <= end:
            slots.append(current.time())
            current += step
        return slots

    def free_slots(self, day):
        """Time slots on `day` that are not already booked."""
        if day in self.unavailable_date_set():
            return []
        booked = set(
            self.appointments.filter(date=day).exclude(status='Cancelled').values_list('time', flat=True)
        )
        return [t for t in self.time_slots() if t not in booked]




class Laboratory(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='laboratory')
    lab_id = models.CharField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.lab_id:
            self.lab_id = generate_unique_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - Laboratory"

class Pharmacy(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pharmacy')
    pharmacy_id = models.CharField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pharmacy_id:
            self.pharmacy_id = generate_unique_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - Pharmacy"

class Prescription(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions', to_field='patient_id', db_column='patient_id')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prescribed_by')
    medicine_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100)
    instructions = models.TextField()
    status = models.CharField(max_length=20, choices=[('Not Fulfilled', 'Not Fulfilled'), ('Fulfilled', 'Fulfilled')], default='Not Fulfilled')
    date_prescribed = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicine_name} - {self.patient}"

class MedicalTest(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="medical_tests")
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, null=True, blank=True)
    test_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=100, 
        choices=[('Pending', 'Pending'), ('Completed', 'Completed')], 
        default='Pending'
    )
    test_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.test_name} - {self.patient.user.username}"


class MedicalHistory(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="medical_history")
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="updated_medical_histories")  # ✅ Consistent with prescriptions
    details = models.TextField()
    date_added = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
  

    def __str__(self):
        return f"Medical History for {self.patient.user.username}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('Scheduled', 'Scheduled'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateField()
    time = models.TimeField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'time']

    def __str__(self):
        return f"{self.patient} with {self.doctor} on {self.date} {self.time}"


class ConsentGrant(models.Model):
    """A patient's permission for one other user (doctor, pharmacy or laboratory) to use one part of their record.

    One row per (patient, grantee, scope). A grant is active when it is not revoked and not expired.
    `source` records how it came to exist: the patient gave it, or a doctor used emergency 'break glass' access.
    """
    SCOPE_RECORDS = 'records'            # medical history entries
    SCOPE_PRESCRIPTIONS = 'prescriptions'
    SCOPE_TESTS = 'tests'
    SCOPE_CHOICES = [
        (SCOPE_RECORDS, 'Medical history'),
        (SCOPE_PRESCRIPTIONS, 'Prescriptions'),
        (SCOPE_TESTS, 'Lab tests'),
    ]
    SOURCE_PATIENT = 'patient'
    SOURCE_BREAK_GLASS = 'break_glass'

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='consent_grants')
    grantee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consent_received')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    source = models.CharField(max_length=20, default=SOURCE_PATIENT)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['patient', 'grantee', 'scope'])]

    def is_active(self, now=None):
        from django.utils import timezone
        now = now or timezone.now()
        return self.revoked_at is None and (self.expires_at is None or self.expires_at > now)

    def __str__(self):
        return f"{self.patient} -> {self.grantee} ({self.scope})"


class AccessLog(models.Model):
    """Every decision about access to a patient's record, allowed or denied. Append-only by convention."""
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='access_log_entries')
    actor_role = models.CharField(max_length=20, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='access_log')
    scope = models.CharField(max_length=20)
    action = models.CharField(max_length=40)
    allowed = models.BooleanField()
    basis = models.CharField(max_length=20, blank=True)   # self / grant / treatment / break_glass / none
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.actor_role} {self.action} {self.scope} {'ok' if self.allowed else 'DENIED'}"
