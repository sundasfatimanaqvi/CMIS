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
        return static('icons/default-avatar.png')

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
