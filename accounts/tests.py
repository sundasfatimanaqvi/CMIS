import datetime
import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Appointment, Doctor, Laboratory, MedicalHistory, MedicalTest, Patient,
    Pharmacy, Prescription,
)

PASSWORD = "Str0ng-Pass-123"


def make_user(username, role):
    user = User.objects.create_user(username=username, password=PASSWORD, email=f"{username}@example.com")
    model = {'patient': Patient, 'doctor': Doctor, 'pharmacy': Pharmacy, 'laboratory': Laboratory}[role]
    profile = model.objects.create(user=user)
    return user, profile


def next_weekday_with_slots(doctor, offset=1):
    return timezone.localdate() + datetime.timedelta(days=offset)


class BaseCase(TestCase):
    def setUp(self):
        self.patient_user, self.patient = make_user("pat", "patient")
        self.doctor_user, self.doctor = make_user("doc", "doctor")
        self.pharmacy_user, _ = make_user("pharm", "pharmacy")
        self.lab_user, _ = make_user("lab", "laboratory")

    def login(self, user):
        self.client.force_login(user)

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")


class PublicPagesTests(TestCase):
    def test_public_pages_render(self):
        for name in ("home", "about", "credits", "login", "register"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_navbar_for_logged_in_user_does_not_crash(self):
        user, _ = make_user("someone", "patient")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)


class AuthTests(BaseCase):
    def test_register_creates_user_with_role_and_names(self):
        response = self.client.post(reverse("register"), {
            "username": "newdoc", "first_name": "Nora", "last_name": "Khan",
            "email": "nora@example.com", "password1": PASSWORD, "password2": PASSWORD, "role": "doctor",
        })
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="newdoc")
        self.assertEqual(user.first_name, "Nora")
        self.assertTrue(Doctor.objects.filter(user=user).exists())

    def test_register_rejects_weak_password_and_duplicate_email(self):
        data = {"username": "x1", "email": "pat@example.com", "password1": "123", "password2": "123", "role": "patient"}
        response = self.client.post(reverse("register"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="x1").exists())
        self.assertContains(response, "already exists")

    def test_register_rejects_duplicate_username(self):
        response = self.client.post(reverse("register"), {
            "username": "pat", "email": "other@example.com", "password1": PASSWORD, "password2": PASSWORD, "role": "patient",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username="pat").count(), 1)

    def test_login_redirects_each_role_to_its_dashboard(self):
        expected = {
            "pat": "patient_dashboard", "doc": "doctor_dashboard",
            "pharm": "pharmacy_dashboard", "lab": "laboratory_dashboard",
        }
        for username, url_name in expected.items():
            self.client.logout()
            response = self.client.post(reverse("login"), {"username": username, "password": PASSWORD})
            self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
            self.assertRedirects(self.client.get(reverse("dashboard")), reverse(url_name), fetch_redirect_response=False)

    def test_login_failure_shows_error(self):
        response = self.client.post(reverse("login"), {"username": "pat", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct")

    def test_login_ignores_external_next_url(self):
        response = self.client.post(reverse("login"), {"username": "pat", "password": PASSWORD, "next": "https://evil.example/"})
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.login(self.patient_user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))


class RoleAccessTests(BaseCase):
    def test_anonymous_is_sent_to_login(self):
        for name in ("patient_dashboard", "doctor_dashboard", "pharmacy_dashboard", "laboratory_dashboard", "search_doctor"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse("login"), response["Location"])

    def test_wrong_role_is_redirected(self):
        pairs = [
            (self.patient_user, "doctor_dashboard"),
            (self.patient_user, "pharmacy_dashboard"),
            (self.doctor_user, "patient_dashboard"),
            (self.doctor_user, "pharmacy_dashboard"),
            (self.pharmacy_user, "laboratory_dashboard"),
            (self.lab_user, "doctor_profile"),
        ]
        for user, name in pairs:
            self.login(user)
            response = self.client.get(reverse(name))
            self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False, msg_prefix=f"{user.username} -> {name}")

    def test_patient_cannot_use_doctor_api(self):
        self.login(self.patient_user)
        url = reverse("prescribe_medicine", args=[self.patient.patient_id])
        response = self.post_json(url, {"medicine_name": "A", "dosage": "1", "instructions": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Prescription.objects.count(), 0)

    def test_anonymous_api_call_gets_401_json(self):
        response = self.post_json(reverse("add_medical_history", args=[self.patient.patient_id]), {"details": "x"})
        self.assertEqual(response.status_code, 401)

    def test_all_dashboards_render_for_their_role(self):
        for user, name in [(self.patient_user, "patient_dashboard"), (self.doctor_user, "doctor_dashboard"),
                           (self.pharmacy_user, "pharmacy_dashboard"), (self.lab_user, "laboratory_dashboard")]:
            self.login(user)
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class CsrfTests(BaseCase):
    def test_doctor_endpoints_enforce_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.doctor_user)
        url = reverse("prescribe_medicine", args=[self.patient.patient_id])
        response = client.post(url, data=json.dumps({"medicine_name": "A", "dosage": "1", "instructions": "x"}),
                               content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Prescription.objects.count(), 0)


class DoctorRecordTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.login(self.doctor_user)

    def test_search_patient(self):
        found = self.client.get(reverse("search_patient"), {"patient_id": self.patient.patient_id})
        self.assertTrue(found.json()["exists"])
        missing = self.client.get(reverse("search_patient"), {"patient_id": "nope"})
        self.assertFalse(missing.json()["exists"])

    def test_prescribe_medicine_uses_logged_in_doctor(self):
        url = reverse("prescribe_medicine", args=[self.patient.patient_id])
        response = self.post_json(url, {"medicine_name": "Panadol", "dosage": "500mg", "instructions": "after meals", "doctor_id": 999})
        self.assertEqual(response.status_code, 200)
        prescription = Prescription.objects.get()
        self.assertEqual(prescription.doctor, self.doctor_user)

    def test_prescribe_medicine_validates_input(self):
        url = reverse("prescribe_medicine", args=[self.patient.patient_id])
        self.assertEqual(self.post_json(url, {"medicine_name": "Panadol"}).status_code, 400)
        bad = self.client.post(url, data="not json", content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_prescribe_test_and_history(self):
        self.assertEqual(self.post_json(reverse("prescribe_test", args=[self.patient.patient_id]), {"test_name": "CBC"}).status_code, 200)
        test = MedicalTest.objects.get()
        self.assertEqual((test.doctor, test.status), (self.doctor, "Pending"))

        response = self.post_json(reverse("add_medical_history", args=[self.patient.patient_id]), {"details": "Seasonal flu"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MedicalHistory.objects.get().doctor, self.doctor_user)

    def test_patient_management_page(self):
        response = self.client.get(reverse("patient_management", args=[self.patient.patient_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("patient_management", args=["zzzz"])).status_code, 404)

    def test_profile_update(self):
        response = self.client.post(reverse("doctor_profile"), {
            "username": "doc", "specialization": "Cardiology",
            "start_time": "10:00", "end_time": "14:00", "unavailable_days": "2030-01-01,2030-01-02",
        })
        self.assertRedirects(response, reverse("doctor_profile"))
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.specialization, "Cardiology")
        self.assertEqual(self.doctor.working_hours_start, datetime.time(10, 0))
        self.assertEqual(self.doctor.unavailable_days, "2030-01-01,2030-01-02")

    def test_profile_rejects_bad_hours_and_duplicate_username(self):
        self.client.post(reverse("doctor_profile"), {"username": "doc", "start_time": "15:00", "end_time": "09:00"})
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.working_hours_start, datetime.time(9, 0))

        self.client.post(reverse("doctor_profile"), {"username": "pat"})
        self.doctor_user.refresh_from_db()
        self.assertEqual(self.doctor_user.username, "doc")


class MedicalHistoryAccessTests(BaseCase):
    def test_patient_sees_own_but_not_others(self):
        other_user, other = make_user("pat2", "patient")
        self.login(self.patient_user)
        self.assertEqual(self.client.get(reverse("medical_history", args=[self.patient.patient_id])).status_code, 200)
        self.assertRedirects(self.client.get(reverse("medical_history", args=[other.patient_id])),
                             reverse("dashboard"), fetch_redirect_response=False)

    def test_doctor_can_view_any_but_pharmacy_cannot(self):
        self.login(self.doctor_user)
        self.assertEqual(self.client.get(reverse("medical_history", args=[self.patient.patient_id])).status_code, 200)
        self.login(self.pharmacy_user)
        self.assertEqual(self.client.get(reverse("medical_history", args=[self.patient.patient_id])).status_code, 302)


class AppointmentTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.day = timezone.localdate() + datetime.timedelta(days=2)

    def book(self, **overrides):
        data = {"date": self.day.isoformat(), "time": "10:00", "description": "Checkup"}
        data.update(overrides)
        return self.client.post(reverse("book_appointment", args=[self.doctor.id]), data)

    def test_search_doctor_and_booking_page(self):
        self.login(self.patient_user)
        response = self.client.get(reverse("search_doctor"), {"q": "doc"})
        self.assertContains(response, reverse("book_appointment", args=[self.doctor.id]))
        self.assertEqual(self.client.get(reverse("book_appointment", args=[self.doctor.id])).status_code, 200)

    def test_book_success_and_double_booking_blocked(self):
        self.login(self.patient_user)
        self.assertRedirects(self.book(), reverse("patient_dashboard"))
        appointment = Appointment.objects.get()
        self.assertEqual((appointment.patient, appointment.doctor, appointment.status), (self.patient, self.doctor, "Scheduled"))

        other_user, _ = make_user("pat2", "patient")
        self.login(other_user)
        response = self.book()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_cancelled_slot_can_be_rebooked(self):
        self.login(self.patient_user)
        self.book()
        appointment = Appointment.objects.get()
        self.client.post(reverse("update_appointment", args=[appointment.id]), {"action": "cancel"})
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "Cancelled")
        self.assertRedirects(self.book(), reverse("patient_dashboard"))
        self.assertEqual(Appointment.objects.exclude(status="Cancelled").count(), 1)

    def test_booking_validations(self):
        self.login(self.patient_user)
        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        too_far = (timezone.localdate() + datetime.timedelta(days=60)).isoformat()
        for override in ({"date": yesterday}, {"date": too_far}, {"time": "03:00"}, {"time": "10:15"},
                         {"description": "  "}, {"date": ""}, {"time": ""}):
            self.assertEqual(self.book(**override).status_code, 200, override)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_unavailable_day_is_not_bookable(self):
        self.doctor.unavailable_days = self.day.isoformat()
        self.doctor.save()
        self.login(self.patient_user)
        self.assertEqual(self.book().status_code, 200)
        self.assertEqual(Appointment.objects.count(), 0)
        slots = self.client.get(reverse("doctor_slots", args=[self.doctor.id]), {"date": self.day.isoformat()}).json()
        self.assertEqual(slots["slots"], [])

    def test_slots_endpoint_hides_booked_times(self):
        Appointment.objects.create(patient=self.patient, doctor=self.doctor, date=self.day,
                                   time=datetime.time(10, 0), reason="x")
        self.login(self.patient_user)
        data = self.client.get(reverse("doctor_slots", args=[self.doctor.id]), {"date": self.day.isoformat()}).json()
        self.assertNotIn("10:00", data["slots"])
        self.assertIn("09:00", data["slots"])
        self.assertEqual(self.client.get(reverse("doctor_slots", args=[self.doctor.id]), {"date": "bad"}).status_code, 400)

    def test_only_patients_can_book(self):
        self.login(self.doctor_user)
        self.assertRedirects(self.book(), reverse("dashboard"), fetch_redirect_response=False)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_appointment_permissions(self):
        appointment = Appointment.objects.create(patient=self.patient, doctor=self.doctor, date=self.day,
                                                 time=datetime.time(11, 0), reason="x")
        url = reverse("update_appointment", args=[appointment.id])

        stranger, _ = make_user("pat2", "patient")
        self.login(stranger)
        self.client.post(url, {"action": "cancel"})
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "Scheduled")

        self.login(self.patient_user)  # patients cannot "complete"
        self.client.post(url, {"action": "complete"})
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "Scheduled")

        self.login(self.doctor_user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {"action": "complete"})
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "Completed")

    def test_dashboards_show_appointments(self):
        Appointment.objects.create(patient=self.patient, doctor=self.doctor, date=timezone.localdate(),
                                   time=datetime.time(23, 0), reason="Headache")
        self.login(self.doctor_user)
        response = self.client.get(reverse("doctor_dashboard"))
        self.assertEqual(response.context["today_patients"], 1)
        self.assertContains(response, "Headache")
        self.login(self.patient_user)
        self.assertContains(self.client.get(reverse("patient_dashboard")), "Headache")


class PharmacyAndLabTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.prescription = Prescription.objects.create(
            patient=self.patient, doctor=self.doctor_user, medicine_name="Panadol", dosage="500mg", instructions="x")
        self.test = MedicalTest.objects.create(patient=self.patient, doctor=self.doctor, test_name="CBC")

    def test_pharmacy_lookup(self):
        self.login(self.pharmacy_user)
        response = self.client.get(reverse("pharmacy_lookup"), {"patient_id": self.patient.patient_id})
        self.assertContains(response, "Panadol")
        self.assertRedirects(self.client.get(reverse("pharmacy_lookup"), {"patient_id": "none"}),
                             reverse("pharmacy_dashboard"))

    def test_toggle_prescription_is_post_only_and_pharmacy_only(self):
        url = reverse("toggle_prescription_status", args=[self.prescription.id])
        self.login(self.pharmacy_user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).json()["new_status"], "Fulfilled")
        self.assertEqual(self.client.post(url).json()["new_status"], "Not Fulfilled")

        self.login(self.patient_user)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_laboratory_toggle(self):
        url = reverse("toggle_test_status", args=[self.test.id])
        self.login(self.lab_user)
        self.assertContains(self.client.get(reverse("laboratory_dashboard")), "CBC")
        self.assertEqual(self.client.post(url).json()["new_status"], "Completed")
        self.login(self.doctor_user)
        self.assertEqual(self.client.post(url).status_code, 403)


class ChatbotTests(BaseCase):
    URL = "chatbot_conversation"

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()
        self.login(self.patient_user)

    def ask(self, message):
        return self.post_json(reverse(self.URL), {"message": message})

    def test_only_patients_can_use_it(self):
        self.login(self.doctor_user)
        self.assertEqual(self.ask("headache").status_code, 403)
        self.client.logout()
        self.assertEqual(self.ask("headache").status_code, 401)

    def test_csrf_is_enforced(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.patient_user)
        response = client.post(reverse(self.URL), data=json.dumps({"message": "hi"}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_rejects_empty_and_get(self):
        self.assertEqual(self.ask("   ").status_code, 400)
        self.assertEqual(self.client.post(reverse(self.URL), data="nope", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(reverse(self.URL)).status_code, 405)

    def test_without_api_key_uses_builtin_guidance(self):
        with self.settings(OPENAI_API_KEY=""):
            data = self.ask("I have a headache").json()
        self.assertTrue(data["success"])
        self.assertEqual(data["source"], "builtin")
        self.assertIn("Headache", data["response"])

    def test_ai_reply_is_used_and_urgency_detected(self):
        from unittest import mock
        with mock.patch("accounts.chatbot._call_openai", return_value="Rest well. You should see a doctor soon.") as call:
            data = self.ask("my knee hurts").json()
        call.assert_called_once_with("my knee hurts")  # nothing else (no patient id) is sent
        self.assertEqual((data["source"], data["urgency"]), ("ai", "urgent"))

    def test_api_failure_falls_back(self):
        from unittest import mock
        with mock.patch("accounts.chatbot._call_openai", side_effect=OSError("down")):
            data = self.ask("I have a fever").json()
        self.assertTrue(data["success"])
        self.assertEqual(data["source"], "builtin")

    def test_emergency_is_answered_locally_without_calling_the_api(self):
        from unittest import mock
        with mock.patch("accounts.chatbot._call_openai", side_effect=AssertionError("must not be called")):
            data = self.ask("I have severe chest pain").json()
        self.assertEqual(data["urgency"], "emergency")
        self.assertIn("1122", data["response"])

    def test_nearby_request_returns_map_links(self):
        data = self.ask("find a pharmacy near me").json()
        self.assertIn("google.com/maps", data["response"])

    def test_rate_limit(self):
        from unittest import mock
        with mock.patch("accounts.chatbot.RATE_LIMIT_MESSAGES", 2), self.settings(OPENAI_API_KEY=""):
            self.assertEqual(self.ask("headache").status_code, 200)
            self.assertEqual(self.ask("fever").status_code, 200)
            self.assertEqual(self.ask("cough").status_code, 429)

    def test_widget_only_rendered_for_patients(self):
        self.assertContains(self.client.get(reverse("patient_dashboard")), 'id="chatWindow"')
        self.login(self.doctor_user)
        self.assertNotContains(self.client.get(reverse("doctor_dashboard")), 'id="chatWindow"')
