from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.forms import AuthenticationForm
from .forms import RegistrationForm, PrescribeMedicineForm
from .models import Patient, Doctor, Laboratory, Pharmacy, Prescription, MedicalTest, MedicalHistory
from django.contrib.auth.models import User
from django.contrib import messages
import json



# Simple home view (for your home template)
def home(request):
    return render(request, 'accounts/home.html')

def about(request):
    return render(request, 'accounts/about.html')



def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password1']
            role = form.cleaned_data['role']

            # ✅ Check if username already exists
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username is already taken. Please choose another.")

                print("MESSAGES DEBUG:", list(messages.get_messages(request)))

                return render(request, "accounts/register.html", {"form": form})  # ✅ Keep form data and show error

            # ✅ Create user
            user = User.objects.create_user(username=username, email=email, password=password)
            
            # ✅ Assign user to correct role
            if role == "patient":
                Patient.objects.create(user=user)
            elif role == "doctor":
                Doctor.objects.create(user=user)
            elif role == "laboratory":
                Laboratory.objects.create(user=user)
            elif role == "pharmacy":
                Pharmacy.objects.create(user=user)

            messages.success(request, "Registration successful! Please log in.")
            return redirect("login")  
    else:
        form = RegistrationForm()



    return render(request, "accounts/register.html", {"form": form})




def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Redirect based on the user's stored role
            if Doctor.objects.filter(user=user).exists():
                return redirect('doctor_dashboard')
            elif Laboratory.objects.filter(user=user).exists():
                return redirect('laboratory_dashboard')
            elif Pharmacy.objects.filter(user=user).exists():
                return redirect('pharmacy_dashboard')
            elif Patient.objects.filter(user=user).exists():
                return redirect('patient_dashboard')
            else:
                messages.error(request, "No role found for this user.")
                return redirect('home')

    else:
        form = AuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def dashboard_redirect_view(request):
    user = request.user
    
    if Doctor.objects.filter(user=user).exists():
        return redirect('doctor_dashboard')
    elif Laboratory.objects.filter(user=user).exists():
        return redirect('laboratory_dashboard')
    elif Pharmacy.objects.filter(user=user).exists():
        return redirect('pharmacy_dashboard')
    elif Patient.objects.filter(user=user).exists():
        return redirect('patient_dashboard')
    else:
        messages.error(request, "No role found for this user.")
        return redirect('home')

@login_required
def doctor_dashboard(request):
    # Dummy data for illustration; in a real app fetch from your Appointment model, etc.
    appointments = []  # Replace with your query to fetch doctor's appointments
    context = {
        'appointments': appointments,
        'next_day_appointments': 0,
        'today_patients': 0,
        'total_appointments': 0,
    }
    return render(request, 'accounts/doctor_dashboard.html', context)



@login_required
def patient_dashboard(request):
    patient = get_object_or_404(Patient, user=request.user)
    
    # Fetch Prescriptions
    prescriptions = Prescription.objects.filter(patient=patient).order_by('-date_prescribed')

    # Fetch Prescribed Tests (ordering by test_date instead of date_prescribed)
    prescribed_tests = MedicalTest.objects.filter(patient=patient).order_by('-test_date')

# Fetch Medical History
    medical_history = MedicalHistory.objects.filter(patient=patient).order_by('-date_added')  # Assuming you have a date_added field

    context = {
        'prescriptions': prescriptions,
        'prescribed_tests': prescribed_tests,
        'medical_history': medical_history,  # Add medical history to context
    }

    return render(request, 'accounts/patient_dashboard.html', context)


@login_required
def search_patient(request):
    patient_id = request.GET.get('patient_id')
    exists = Patient.objects.filter(patient_id=patient_id).exists()
    return JsonResponse({'exists': exists})


@login_required
def patient_management(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)

    # Ensure the logged-in user is a doctor
    try:
        doctor = request.user.doctor  
    except Doctor.DoesNotExist:
        return JsonResponse({"error": "Only doctors can manage patient records."}, status=403)

    # Fetch existing data for the patient
    prescriptions = Prescription.objects.filter(patient=patient)
    tests = MedicalTest.objects.filter(patient=patient)
    history_entries = MedicalHistory.objects.filter(patient=patient).order_by("-updated_at")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "prescribe_medicine":

            # Extract data from the request
            medicine_name = request.POST.get("medicine_name")
            dosage = request.POST.get("dosage")
            instructions = request.POST.get("instructions")

            #save data in database
            if medicine_name and dosage and instructions:
                Prescription.objects.create(
                    patient=patient,
                    doctor=doctor,  # ✅ Ensure doctor ID is saved
                    medicine_name=medicine_name,
                    dosage=dosage,
                    instructions=instructions
                )
                return JsonResponse({"message": "Medicine prescribed successfully"}, status=200)
        
        elif action == "prescribe_test":
            test_name = request.POST.get("test_name")

            if test_name:
                MedicalTest.objects.create(
                    patient=patient,
                    doctor=doctor,  # ✅ Ensure doctor ID is saved
                    test_name=test_name
                )
                return JsonResponse({"message": "Test prescribed successfully"}, status=200)

        elif action == "update_medical_history":
            history_text = request.POST.get("history_text")

            if history_text:
                MedicalHistory.objects.create(
                    patient=patient,
                    doctor=doctor,  # ✅ Ensure doctor ID is saved
                    history_text=history_text
                )
                return JsonResponse({"message": "Medical history updated successfully"}, status=200)

    return render(request, "accounts/patient_management.html", {
        "patient": patient,
        "prescriptions": prescriptions,
        "tests": tests,
        "history_entries": history_entries,
    })


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


def search_doctor(request):
    doctors = Doctor.objects.all()
    return render(request, "accounts/search_doctor.html", {"doctors": doctors})


@login_required
def doctor_profile(request):
    doctor = request.user.doctor  
    if request.method == "POST":
        username = request.POST.get("username", doctor.user.username).strip()
        if username:
            doctor.user.username = username
        else:
            messages.error(request, "Username cannot be empty.")
            return redirect("doctor_profile")

        if request.POST.get("password"):
            doctor.user.set_password(request.POST["password"])

        if request.FILES.get("profile_picture"):
            doctor.profile_picture = request.FILES["profile_picture"]

        start_time = request.POST.get("start_time")
        end_time = request.POST.get("end_time")
        unavailable_days = request.POST.get("unavailable_days", "")

        if start_time:
            doctor.working_hours_start = start_time
        if end_time:
            doctor.working_hours_end = end_time
        if unavailable_days:
            doctor.unavailable_dates = {"unavailable_days": unavailable_days.split(",")}
        
        doctor.user.save()
        doctor.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("doctor_profile")
    
    return render(request, "accounts/doctor_profile.html", {"doctor": doctor})


from django.views.decorators.http import require_POST

@login_required
def pharmacy_dashboard(request):
    return render(request, 'accounts/pharmacy_dashboard.html')

@login_required
def pharmacy_lookup(request):
    patient_id = request.POST.get("patient_id") or request.GET.get("patient_id")
    if not patient_id:
        return redirect('pharmacy_dashboard')

    patient = Patient.objects.filter(patient_id=patient_id).first()
    if not patient:
        messages.error(request, "No patient found with this ID.")
        return redirect('pharmacy_dashboard')

    prescriptions = Prescription.objects.filter(patient=patient)
    return render(request, "accounts/pharmacy_lookup.html", {
        "patient": patient,
        "patient_id": patient_id,
        "prescriptions": prescriptions
    })

@login_required
def toggle_prescription_status(request, prescription_id):
    prescription = get_object_or_404(Prescription, id=prescription_id)
    if prescription.status == "Fulfilled":
        prescription.status = "Not Fulfilled"
    else:
        prescription.status = "Fulfilled"
    prescription.save()
    return JsonResponse({"success": True, "new_status": prescription.status})






import json

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json
from accounts.models import Prescription, Patient, Doctor



@csrf_exempt
def prescribe_medicine(request, patient_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            print("Received data:", data)  # Debugging

            doctor_id = data.get("doctor_id")
            medicine_name = data.get("medicine_name")
            dosage = data.get("dosage")
            instructions = data.get("instructions")

            # Get Patient and Doctor objects
            patient = get_object_or_404(Patient, patient_id=patient_id)
            doctor = get_object_or_404(Doctor, id=doctor_id)

            # Validate input fields
            if not all([medicine_name, dosage, instructions]):
                return JsonResponse({"success": False, "error": "All fields are required."}, status=400)

            # Save to database correctly (Assign the User instance)
            Prescription.objects.create(
                patient=patient,
                doctor=doctor.user,  # ✅ Assign User instance instead of Doctor instance
                medicine_name=medicine_name,
                dosage=dosage,
                instructions=instructions
            )

            return JsonResponse({"success": True, "message": "Prescription saved successfully!"})
        
        except Exception as e:
            print(f"Error: {str(e)}")  # Debugging
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


import json


def prescribe_test(request, patient_id):
    if request.method == "POST":
        try:
            raw_body = request.body.decode("utf-8")
            print("Raw Request Body:", raw_body)  # Debugging

            if not raw_body:
                return JsonResponse({"success": False, "error": "Empty request body"}, status=400)

            data = json.loads(raw_body)

            # Required fields check
            test_name = data.get("test_name")
            doctor_id = data.get("doctor_id")

            if not test_name or not doctor_id:
                return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)

            # Patient and Doctor objects fetch karna
            patient = get_object_or_404(Patient, patient_id=patient_id)
            doctor = get_object_or_404(Doctor, id=doctor_id)

            # Test record save karna
            test = MedicalTest.objects.create(
                patient=patient,
                doctor=doctor,
                test_name=test_name,
                status="Pending"
            )

            return JsonResponse({"success": True, "message": "Test prescribed successfully!", "test_id": test.id})

        except json.JSONDecodeError as e:
            print("JSON Decode Error:", str(e))  # Debugging
            return JsonResponse({"success": False, "error": "Invalid JSON format"}, status=400)

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


def get_patient_tests(request, patient_id):
    try:
        patient = get_object_or_404(Patient, id=patient_id)
        tests = MedicalTest.objects.filter(patient=patient).values("test_name", "status", "test_date")

        return JsonResponse({"success": True, "tests": list(tests)})
    
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)



import json
from django.http import JsonResponse

@csrf_exempt
def add_medical_history(request, patient_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            # Fetch the patient without converting patient_id to int
            patient = Patient.objects.get(patient_id=patient_id)  
            doctor = request.user  

            MedicalHistory.objects.create(
                patient=patient,
                doctor=doctor,
                details=data.get("details")
            )

            return JsonResponse({"success": True, "message": "Medical history added successfully!"})
        except Patient.DoesNotExist:
            return JsonResponse({"success": False, "error": "Patient not found"}, status=400)
        except User.DoesNotExist:
            return JsonResponse({"success": False, "error": "Doctor not found"}, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

@login_required
def view_medical_history(request, patient_id):
    patient = get_object_or_404(Patient, patient_id=patient_id)
    history_entries = MedicalHistory.objects.filter(patient=patient).order_by("-updated_at")

    return render(request, "accounts/medical_history.html", {"patient": patient, "history_entries": history_entries})
