"""Create demo accounts for local development: python manage.py seed_demo"""
import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import (
    Appointment, Doctor, Laboratory, MedicalHistory, MedicalTest, Patient,
    Pharmacy, Prescription,
)

PASSWORD = "Healio-demo-123"


class Command(BaseCommand):
    help = "Create demo patient, doctors, pharmacy and laboratory accounts (development only)."

    def handle(self, *args, **options):
        def user(username, first, last):
            obj, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": f"{username}@example.com"},
            )
            if created:
                obj.set_password(PASSWORD)
                obj.save()
            return obj

        doctors = []
        for username, first, last, spec in [
            ("dr_khan", "Fatima", "Khan", "Cardiology"),
            ("dr_ali", "Sana", "Ali", "Neurology"),
            ("dr_raza", "Ali", "Raza", "Pediatrics"),
        ]:
            doctor, _ = Doctor.objects.get_or_create(user=user(username, first, last), defaults={"specialization": spec})
            doctors.append(doctor)

        patient, _ = Patient.objects.get_or_create(user=user("demo_patient", "Demo", "Patient"))
        Pharmacy.objects.get_or_create(user=user("demo_pharmacy", "Demo", "Pharmacy"))
        Laboratory.objects.get_or_create(user=user("demo_lab", "Demo", "Lab"))

        if not patient.appointments.exists():
            day = timezone.localdate() + datetime.timedelta(days=1)
            Appointment.objects.create(patient=patient, doctor=doctors[0], date=day, time=datetime.time(10, 0), reason="Chest pain follow-up")
            Prescription.objects.create(patient=patient, doctor=doctors[0].user, medicine_name="Aspirin", dosage="75 mg daily", instructions="Take after breakfast")
            MedicalTest.objects.create(patient=patient, doctor=doctors[0], test_name="Lipid profile")
            MedicalHistory.objects.create(patient=patient, doctor=doctors[0].user, details="Mild hypertension, monitor blood pressure weekly.")

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Log in as dr_khan / demo_patient / demo_pharmacy / demo_lab with password {PASSWORD}\n"
            f"Demo patient ID: {patient.patient_id}"
        ))
