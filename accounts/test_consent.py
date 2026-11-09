import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import consent
from .models import AccessLog, Appointment, ConsentGrant, MedicalHistory, MedicalTest, Prescription
from .tests import BaseCase, make_user


class ConsentRuleTests(BaseCase):
    def test_stranger_is_denied_and_logged(self):
        self.assertFalse(consent.check_access(self.doctor_user, self.patient, 'records', 'view_history'))
        entry = AccessLog.objects.get()
        self.assertFalse(entry.allowed)
        self.assertEqual((entry.basis, entry.actor, entry.patient), ('none', self.doctor_user, self.patient))

    def test_patient_can_always_access_self_but_not_others(self):
        _, other = make_user("pat2", "patient")
        self.assertTrue(consent.check_access(self.patient_user, self.patient, 'records', 'x'))
        self.assertFalse(consent.check_access(self.patient_user, other, 'records', 'x'))

    def test_grant_is_per_scope(self):
        consent.grant(self.patient, self.doctor_user, ['records'])
        self.assertTrue(consent.check_access(self.doctor_user, self.patient, 'records', 'x'))
        self.assertFalse(consent.check_access(self.doctor_user, self.patient, 'tests', 'x'))

    def test_grant_is_per_patient(self):
        _, other = make_user("pat2", "patient")
        consent.grant(self.patient, self.doctor_user, consent.SCOPES)
        self.assertFalse(consent.check_access(self.doctor_user, other, 'records', 'x'))

    def test_revoked_and_expired_grants_do_not_count(self):
        consent.grant(self.patient, self.doctor_user, ['records'])
        g = ConsentGrant.objects.get()
        g.expires_at = timezone.now() - datetime.timedelta(minutes=1)
        g.save()
        self.assertFalse(consent.check_access(self.doctor_user, self.patient, 'records', 'x'))
        g.expires_at = None
        g.save()
        self.assertTrue(consent.check_access(self.doctor_user, self.patient, 'records', 'x'))
        consent.revoke(g)
        self.assertFalse(consent.check_access(self.doctor_user, self.patient, 'records', 'x'))

    def test_granting_twice_does_not_duplicate(self):
        consent.grant(self.patient, self.doctor_user, ['records'])
        consent.grant(self.patient, self.doctor_user, ['records'])
        self.assertEqual(ConsentGrant.objects.count(), 1)

    def test_appointment_gives_treatment_access_to_that_doctor_only(self):
        other_doc_user, _ = make_user("doc2", "doctor")
        Appointment.objects.create(patient=self.patient, doctor=self.doctor, date=timezone.localdate(),
                                   time=datetime.time(10, 0), reason="x")
        self.assertEqual(consent.access_basis(self.doctor_user, self.patient, 'records'), 'treatment')
        self.assertIsNone(consent.access_basis(other_doc_user, self.patient, 'records'))

    def test_cancelled_appointment_gives_no_access(self):
        Appointment.objects.create(patient=self.patient, doctor=self.doctor, date=timezone.localdate(),
                                   time=datetime.time(10, 0), reason="x", status="Cancelled")
        self.assertIsNone(consent.access_basis(self.doctor_user, self.patient, 'records'))

    def test_pharmacy_gets_no_implicit_access(self):
        Appointment.objects.create(patient=self.patient, doctor=self.doctor, date=timezone.localdate(),
                                   time=datetime.time(10, 0), reason="x")
        self.assertIsNone(consent.access_basis(self.pharmacy_user, self.patient, 'prescriptions'))


class ConsentEnforcementTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.prescription = Prescription.objects.create(
            patient=self.patient, doctor=self.doctor_user, medicine_name="Panadol", dosage="500mg", instructions="x")
        self.test = MedicalTest.objects.create(patient=self.patient, doctor=self.doctor, test_name="CBC")

    def test_doctor_without_consent_is_blocked_everywhere(self):
        self.login(self.doctor_user)
        pid = self.patient.patient_id
        self.assertEqual(self.client.get(reverse("patient_management", args=[pid])).status_code, 403)
        self.assertEqual(self.client.get(reverse("medical_history", args=[pid])).status_code, 403)
        self.assertEqual(self.post_json(reverse("prescribe_medicine", args=[pid]),
                                        {"medicine_name": "A", "dosage": "1", "instructions": "x"}).status_code, 403)
        self.assertEqual(self.post_json(reverse("prescribe_test", args=[pid]), {"test_name": "CBC"}).status_code, 403)
        self.assertEqual(self.post_json(reverse("add_medical_history", args=[pid]), {"details": "x"}).status_code, 403)
        self.assertEqual(Prescription.objects.count(), 1)
        self.assertEqual(MedicalHistory.objects.count(), 0)
        self.assertTrue(AccessLog.objects.filter(allowed=False).count() >= 5)

    def test_pharmacy_without_consent_cannot_see_or_change(self):
        self.login(self.pharmacy_user)
        response = self.client.get(reverse("pharmacy_lookup"), {"patient_id": self.patient.patient_id})
        self.assertRedirects(response, reverse("pharmacy_dashboard"), fetch_redirect_response=False)
        response = self.client.post(reverse("toggle_prescription_status", args=[self.prescription.id]))
        self.assertEqual(response.status_code, 403)
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.status, "Not Fulfilled")

    def test_pharmacy_with_prescription_consent_only_cannot_touch_tests(self):
        consent.grant(self.patient, self.pharmacy_user, ['prescriptions'])
        self.login(self.pharmacy_user)
        self.assertEqual(self.client.post(reverse("toggle_prescription_status", args=[self.prescription.id])).status_code, 200)

    def test_lab_only_sees_tests_of_patients_who_shared(self):
        other_user, other = make_user("pat2", "patient")
        MedicalTest.objects.create(patient=other, doctor=self.doctor, test_name="HIDDEN-LIPID")
        consent.grant(self.patient, self.lab_user, ['tests'])
        self.login(self.lab_user)
        page = self.client.get(reverse("laboratory_dashboard"))
        self.assertEqual(page.context["pending_count"], 1)
        self.assertNotContains(page, "HIDDEN-LIPID")
        self.assertEqual(self.client.post(reverse("toggle_test_status", args=[self.test.id])).status_code, 200)
        hidden = MedicalTest.objects.get(test_name="HIDDEN-LIPID")
        self.assertEqual(self.client.post(reverse("toggle_test_status", args=[hidden.id])).status_code, 403)

    def test_break_glass_needs_reason_gives_24h_access_and_is_visible_to_patient(self):
        self.login(self.doctor_user)
        url = reverse("break_glass", args=[self.patient.patient_id])
        self.assertEqual(self.client.post(url, {"reason": "short"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("patient_management", args=[self.patient.patient_id])).status_code, 403)
        response = self.client.post(url, {"reason": "Patient unconscious in emergency room"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("patient_management", args=[self.patient.patient_id])).status_code, 200)
        grant = ConsentGrant.objects.filter(source='break_glass').first()
        self.assertLess(grant.expires_at, timezone.now() + datetime.timedelta(hours=25))
        self.assertTrue(AccessLog.objects.filter(action='break_glass', allowed=True).exists())
        self.login(self.patient_user)
        self.assertContains(self.client.get(reverse("sharing_access")), "Emergency access")

    def test_break_glass_is_doctor_only_and_post_only(self):
        url = reverse("break_glass", args=[self.patient.patient_id])
        self.login(self.pharmacy_user)
        self.assertEqual(self.client.post(url, {"reason": "Patient unconscious in emergency room"}).status_code, 302)
        self.assertFalse(ConsentGrant.objects.exists())
        self.login(self.doctor_user)
        self.assertEqual(self.client.get(url).status_code, 405)


class SharingPageTests(BaseCase):
    def test_patient_can_grant_and_revoke(self):
        self.login(self.patient_user)
        self.assertEqual(self.client.get(reverse("sharing_access")).status_code, 200)
        self.client.post(reverse("consent_grant"), {"username": "doc", "scopes": ["records", "tests"], "days": "7"})
        self.assertEqual(ConsentGrant.objects.filter(grantee=self.doctor_user).count(), 2)
        self.assertIsNotNone(ConsentGrant.objects.first().expires_at)
        grant = ConsentGrant.objects.first()
        self.client.post(reverse("consent_revoke", args=[grant.id]))
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)

    def test_cannot_grant_to_another_patient_or_unknown_user(self):
        make_user("pat2", "patient")
        self.login(self.patient_user)
        self.client.post(reverse("consent_grant"), {"username": "pat2", "scopes": ["records"]})
        self.client.post(reverse("consent_grant"), {"username": "nobody", "scopes": ["records"]})
        self.client.post(reverse("consent_grant"), {"username": "doc"})
        self.assertFalse(ConsentGrant.objects.exists())

    def test_patient_cannot_revoke_someone_elses_grant(self):
        other_user, other = make_user("pat2", "patient")
        consent.grant(other, self.doctor_user, ['records'])
        grant = ConsentGrant.objects.get()
        self.login(self.patient_user)
        self.assertEqual(self.client.post(reverse("consent_revoke", args=[grant.id])).status_code, 404)

    def test_only_patients_reach_the_sharing_pages(self):
        self.login(self.doctor_user)
        self.assertEqual(self.client.get(reverse("sharing_access")).status_code, 302)
        self.assertEqual(self.client.post(reverse("consent_grant"), {"username": "pharm", "scopes": ["records"]}).status_code, 302)
        self.assertFalse(ConsentGrant.objects.exists())

    def test_access_log_shows_blocked_attempts(self):
        consent.check_access(self.doctor_user, self.patient, 'records', 'view_history')
        self.login(self.patient_user)
        page = self.client.get(reverse("sharing_access"))
        self.assertContains(page, "Blocked")
        self.assertContains(page, "view_history")
