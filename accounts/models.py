import uuid
from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import render

def generate_unique_id():
    # Generates a unique 8-character ID (you can adjust as needed)
    return str(uuid.uuid4())[:8]

def home(request):
    doctors = Doctor.objects.all()[:6]  # Fetch at least 6 doctors
    return render(request, 'home.html', {'doctors': doctors})

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


    def save(self, *args, **kwargs):
        if not self.doctor_id:
            self.doctor_id = generate_unique_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - Doctor"
    




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
