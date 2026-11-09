import datetime
import json

from django import forms
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .decorators import (
    doctor_required, get_role, laboratory_required, patient_required,
    pharmacy_required, role_required,
)
from .forms import RegistrationForm
from .models import (
    Appointment, Doctor, Laboratory, MedicalHistory, MedicalTest, Patient,
    Pharmacy, Prescription,
)

BOOKING_WINDOW_DAYS = 14
MAX_PROFILE_PICTURE_BYTES = 2 * 1024 * 1024


# --------------------------------------------------------------------------- #
# Public pages
# --------------------------------------------------------------------------- #
def home(request):
    return render(request, 'accounts/home.html')


def about(request):
    return render(request, 'accounts/about.html')


# Flaticon icons used in static/icons/ (free licence: attribution required).
ICON_CREDITS = [
    ("doctor-appointment.png", "Doctor appointment", "juicy_fish", 10476232),
    ("hospital-building.png", "Hospital building", "juicy_fish", 2749678),
    ("pharmacy.png", "Pharmacy", "Magnific", 1686939),
    ("stethoscope.png", "Stethoscope", "Magnific", 2002576),
    ("medicine.png", "Medicine", "Magnific", 3022827),
    ("blood-test.png", "Blood test", "Magnific", 3127109),
    ("flask.png", "Flask", "Magnific", 3655592),
    ("medical-record.png", "Medical record", "Magnific", 4003790),
    ("medical-records.png", "Medical records", "Magnific", 4193443),
    ("healthcare.png", "Healthcare", "Magnific", 5024446),
    ("doctor.png", "Doctor", "Andyarteicon", 4837211),
    ("doctor-female.png", "Doctor", "Andyarteicon", 4837219),
    ("lab-technician.png", "Lab technician", "smashingstocks", 6401477),
]


def credits(request):
    return render(request, 'accounts/credits.html', {'icons': ICON_CREDITS})


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
ROLE_MODELS = {
    'patient': Patient,
    'doctor': Doctor,
    'laboratory': Laboratory,
    'pharmacy': Pharmacy,
}

ROLE_DASHBOARDS = {
    'doctor': 'doctor_dashboard',
    'laboratory': 'laboratory_dashboard',
    'pharmacy': 'pharmacy_dashboard',
    'patient': 'patient_dashboard',
}


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data['username'],
                    email=data['email'],
                    password=data['password1'],
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                )
                ROLE_MODELS[data['role']].objects.create(user=user)

            messages.success(request, "Registration successful! Please log in.")
            return redirect("login")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form, 'next': request.GET.get('next', '')})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


@login_required
def dashboard_redirect_view(request):
    role = get_role(request.user)
    if role:
        return redirect(ROLE_DASHBOARDS[role])
    messages.error(request, "No role found for this user.")
    return redirect('home')


# --------------------------------------------------------------------------- #
# Doctor
# --------------------------------------------------------------------------- #
@doctor_required
def doctor_dashboard(request):
    doctor = request.user.doctor
    today = timezone.localdate()
    tomorrow = today + datetime.timedelta(days=1)

    appointments = doctor.appointments.select_related('patient__user')
    active = appointments.exclude(status='Cancelled')

    context = {
        'doctor': doctor,
        'appointments': appointments.filter(date__gte=today).order_by('date', 'time'),
        'next_day_appointments': active.filter(date=tomorrow).count(),
        'today_patients': active.filter(date=today).count(),
        'total_appointments': active.count(),
    }
    return render(request, 'accounts/doctor_dashboard.html', context)


@doctor_required
def doctor_profile(request):
    doctor = request.user.doctor

    if request.method == "POST":
        user = doctor.user
        errors = []

        username = request.POST.get("username", "").strip()
        if not username:
            errors.append("Username cannot be empty.")
        elif User.objects.filter(username=username).exclude(pk=user.pk).exists():
            errors.append("That username is already taken.")

        start = _parse_time(request.POST.get("start_time"))
        end = _parse_time(request.POST.get("end_time"))
        if request.POST.get("start_time") and start is None:
            errors.append("Start time is not valid.")
        if request.POST.get("end_time") and end is None:
            errors.append("End time is not valid.")
        start = start or doctor.working_hours_start
        end = end or doctor.working_hours_end
        if start >= end:
            errors.append("Working hours must end after they start.")

        days = []
        for chunk in request.POST.get("unavailable_days", "").split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                days.append(datetime.date.fromisoformat(chunk).isoformat())
            except ValueError:
                errors.append(f"'{chunk}' is not a valid date.")

        picture = request.FILES.get("profile_picture")
        if picture:
            if picture.size > MAX_PROFILE_PICTURE_BYTES:
                errors.append("Profile picture must be smaller than 2 MB.")
            else:
                try:
                    forms.ImageField().clean(picture)
                except forms.ValidationError:
                    errors.append("Upload a valid image file.")

        password = request.POST.get("password")
        if password:
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            try:
                validate_password(password, user)
            except ValidationError as exc:
                errors.extend(exc.messages)

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect("doctor_profile")

        user.username = username
        if password:
            user.set_password(password)
        user.save()
        if password:
            update_session_auth_hash(request, user)

        doctor.specialization = request.POST.get("specialization", doctor.specialization).strip()[:100]
        doctor.working_hours_start = start
        doctor.working_hours_end = end
        doctor.unavailable_days = ",".join(sorted(set(days)))
        if picture:
            doctor.profile_picture = picture
        doctor.save()

        messages.success(request, "Profile updated successfully.")
        return redirect("doctor_profile")

    return render(request, "accounts/doctor_profile.html", {"doctor": doctor})


def _parse_time(value):
    if not value:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


@role_required('doctor', api=True)
@require_GET
def search_patient(request):
    patient_id = request.GET.get('patient_id', '').strip()
    exists = bool(patient_id) and Patient.objects.filter(patient_id=patient_id).exists()
    return JsonResponse({'exists': exists})


@doctor_required
def patient_management(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)
    return render(request, "accounts/patient_management.html", {
        "patient": patient,
        "prescriptions": Prescription.objects.filter(patient=patient).select_related('doctor').order_by('-date_prescribed'),
        "tests": MedicalTest.objects.filter(patient=patient).select_related('doctor__user').order_by('-test_date'),
        "history_entries": MedicalHistory.objects.filter(patient=patient).select_related('doctor').order_by("-updated_at"),
    })


def _json_body(request):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _clean_text(data, key, max_length):
    value = data.get(key)
    if not isinstance(value, str):
        return ''
    return value.strip()[:max_length]


@role_required('doctor', api=True)
@require_POST
def prescribe_medicine(request, patient_id):
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Invalid JSON format."}, status=400)

    patient = get_object_or_404(Patient, patient_id=patient_id)
    medicine_name = _clean_text(data, "medicine_name", 255)
    dosage = _clean_text(data, "dosage", 100)
    instructions = _clean_text(data, "instructions", 2000)
    if not (medicine_name and dosage and instructions):
        return JsonResponse({"success": False, "error": "All fields are required."}, status=400)

    Prescription.objects.create(
        patient=patient,
        doctor=request.user,
        medicine_name=medicine_name,
        dosage=dosage,
        instructions=instructions,
    )
    return JsonResponse({"success": True, "message": "Prescription saved successfully!"})


@role_required('doctor', api=True)
@require_POST
def prescribe_test(request, patient_id):
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Invalid JSON format."}, status=400)

    patient = get_object_or_404(Patient, patient_id=patient_id)
    test_name = _clean_text(data, "test_name", 255)
    if not test_name:
        return JsonResponse({"success": False, "error": "Test name is required."}, status=400)

    test = MedicalTest.objects.create(
        patient=patient,
        doctor=request.user.doctor,
        test_name=test_name,
        status="Pending",
    )
    return JsonResponse({"success": True, "message": "Test prescribed successfully!", "test_id": test.id})


@role_required('doctor', api=True)
@require_POST
def add_medical_history(request, patient_id):
    data = _json_body(request)
    if data is None:
        return JsonResponse({"success": False, "error": "Invalid JSON format."}, status=400)

    patient = get_object_or_404(Patient, patient_id=patient_id)
    details = _clean_text(data, "details", 5000)
    if not details:
        return JsonResponse({"success": False, "error": "Details are required."}, status=400)

    MedicalHistory.objects.create(patient=patient, doctor=request.user, details=details)
    return JsonResponse({"success": True, "message": "Medical history added successfully!"})


@login_required
def view_medical_history(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)
    role = get_role(request.user)
    # Patients may only read their own record; doctors may read any patient's.
    if role == 'patient' and request.user.patient != patient:
        messages.error(request, "You can only view your own medical history.")
        return redirect('dashboard')
    if role not in ('patient', 'doctor'):
        messages.error(request, "You do not have access to medical records.")
        return redirect('dashboard')

    history_entries = MedicalHistory.objects.filter(patient=patient).select_related('doctor').order_by("-updated_at")
    return render(request, "accounts/medical_history.html", {
        "patient": patient,
        "history_entries": history_entries,
    })


# --------------------------------------------------------------------------- #
# Patient: dashboard, doctor search, appointments
# --------------------------------------------------------------------------- #
@patient_required
def patient_dashboard(request):
    patient = request.user.patient
    today = timezone.localdate()
    appointments = patient.appointments.select_related('doctor__user')

    context = {
        'patient': patient,
        'upcoming_appointments': appointments.filter(date__gte=today, status='Scheduled'),
        'past_appointments': appointments.exclude(date__gte=today, status='Scheduled').order_by('-date', '-time'),
        'prescriptions': Prescription.objects.filter(patient=patient).select_related('doctor').order_by('-date_prescribed'),
        'prescribed_tests': MedicalTest.objects.filter(patient=patient).select_related('doctor__user').order_by('-test_date'),
        'medical_history': MedicalHistory.objects.filter(patient=patient).select_related('doctor').order_by('-date_added'),
    }
    return render(request, 'accounts/patient_dashboard.html', context)


@login_required
def search_doctor(request):
    query = request.GET.get('q', '').strip()
    doctors = Doctor.objects.select_related('user').order_by('user__first_name', 'user__username')
    if query:
        doctors = doctors.filter(
            Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(specialization__icontains=query)
        )
    page = Paginator(doctors, 9).get_page(request.GET.get('page'))
    return render(request, "accounts/search_doctor.html", {
        "page": page,
        "query": query,
        "is_patient": get_role(request.user) == 'patient',
    })


def _slots_for_day(doctor, day):
    """Free slots for `day`, hiding slots that are already in the past today."""
    slots = doctor.free_slots(day)
    now = timezone.localtime()
    if day == now.date():
        slots = [t for t in slots if t > now.time()]
    return slots


def _bookable_dates(doctor):
    today = timezone.localdate()
    days = [today + datetime.timedelta(days=i) for i in range(BOOKING_WINDOW_DAYS + 1)]
    return [d for d in days if _slots_for_day(doctor, d)]


@role_required('patient', api=True)
@require_GET
def doctor_slots(request, doctor_id):
    doctor = get_object_or_404(Doctor, pk=doctor_id)
    try:
        day = datetime.date.fromisoformat(request.GET.get('date', ''))
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid date."}, status=400)
    return JsonResponse({"success": True, "slots": [t.strftime('%H:%M') for t in _slots_for_day(doctor, day)]})


@patient_required
def book_appointment(request, doctor_id):
    doctor = get_object_or_404(Doctor.objects.select_related('user'), pk=doctor_id)
    patient = request.user.patient

    if request.method == "POST":
        reason = request.POST.get("description", "").strip()[:1000]
        try:
            day = datetime.date.fromisoformat(request.POST.get("date", ""))
        except ValueError:
            day = None
        slot = _parse_time(request.POST.get("time"))

        error = None
        today = timezone.localdate()
        if day is None or slot is None:
            error = "Please choose a date and a time."
        elif not reason:
            error = "Please tell the doctor the reason for your visit."
        elif day < today or day > today + datetime.timedelta(days=BOOKING_WINDOW_DAYS):
            error = f"Appointments can be booked up to {BOOKING_WINDOW_DAYS} days ahead."

        if error is None:
            with transaction.atomic():
                # Lock the doctor row so two patients cannot take the same slot.
                Doctor.objects.select_for_update().get(pk=doctor.pk)
                if slot not in _slots_for_day(doctor, day):
                    error = "That time is no longer available. Please pick another one."
                else:
                    Appointment.objects.create(
                        patient=patient, doctor=doctor, date=day, time=slot, reason=reason,
                    )

        if error is None:
            messages.success(request, f"Appointment booked with Dr. {doctor.display_name} on {day:%b %d, %Y} at {slot:%H:%M}.")
            return redirect('patient_dashboard')
        messages.error(request, error)

    return render(request, "accounts/book_appointment.html", {
        "doctor": doctor,
        "patient": patient,
        "available_dates": [d.isoformat() for d in _bookable_dates(doctor)],
        "selected": {
            "date": request.POST.get("date", ""),
            "time": request.POST.get("time", ""),
            "description": request.POST.get("description", ""),
        },
    })


@login_required
@require_POST
def update_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    action = request.POST.get("action")
    role = get_role(request.user)

    if role == 'patient' and appointment.patient.user_id == request.user.id and action == 'cancel':
        new_status = 'Cancelled'
    elif role == 'doctor' and appointment.doctor.user_id == request.user.id and action in ('cancel', 'complete'):
        new_status = 'Cancelled' if action == 'cancel' else 'Completed'
    else:
        messages.error(request, "You cannot change this appointment.")
        return redirect('dashboard')

    if appointment.status != 'Scheduled':
        messages.error(request, "Only scheduled appointments can be changed.")
    else:
        appointment.status = new_status
        appointment.save(update_fields=['status'])
        messages.success(request, f"Appointment marked as {new_status.lower()}.")
    return redirect('dashboard')


# --------------------------------------------------------------------------- #
# Pharmacy
# --------------------------------------------------------------------------- #
@pharmacy_required
def pharmacy_dashboard(request):
    return render(request, 'accounts/pharmacy_dashboard.html')


@pharmacy_required
def pharmacy_lookup(request):
    patient_id = (request.POST.get("patient_id") or request.GET.get("patient_id") or "").strip()
    if not patient_id:
        return redirect('pharmacy_dashboard')

    patient = Patient.objects.filter(patient_id=patient_id).first()
    if not patient:
        messages.error(request, "No patient found with this ID.")
        return redirect('pharmacy_dashboard')

    prescriptions = Prescription.objects.filter(patient=patient).select_related('doctor').order_by('-date_prescribed')
    return render(request, "accounts/pharmacy_lookup.html", {
        "patient": patient,
        "patient_id": patient_id,
        "prescriptions": prescriptions,
    })


@role_required('pharmacy', api=True)
@require_POST
def toggle_prescription_status(request, prescription_id):
    prescription = get_object_or_404(Prescription, id=prescription_id)
    prescription.status = "Not Fulfilled" if prescription.status == "Fulfilled" else "Fulfilled"
    prescription.save(update_fields=['status'])
    return JsonResponse({"success": True, "new_status": prescription.status})


# --------------------------------------------------------------------------- #
# Laboratory
# --------------------------------------------------------------------------- #
@laboratory_required
def laboratory_dashboard(request):
    tests = MedicalTest.objects.select_related('patient__user', 'doctor__user').order_by('status', '-test_date')
    patient_id = request.GET.get('patient_id', '').strip()
    if patient_id:
        tests = tests.filter(patient__patient_id=patient_id)
    return render(request, 'accounts/laboratory_dashboard.html', {
        'tests': tests[:100],
        'patient_id': patient_id,
        'pending_count': MedicalTest.objects.filter(status='Pending').count(),
    })


@role_required('laboratory', api=True)
@require_POST
def toggle_test_status(request, test_id):
    test = get_object_or_404(MedicalTest, pk=test_id)
    test.status = "Pending" if test.status == "Completed" else "Completed"
    test.save(update_fields=['status'])
    return JsonResponse({"success": True, "new_status": test.status})
