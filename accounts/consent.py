"""Patient consent and access auditing.

Rule for reading or changing a patient's data (scope = records / prescriptions / tests):
  1. the patient themself: always allowed;
  2. a doctor with a Scheduled or Completed appointment with the patient: allowed ('treatment');
  3. any user holding an active ConsentGrant for that scope: allowed ('grant');
  4. otherwise denied. A doctor may use emergency access (`break_glass`): it needs a written reason, lasts
     24 hours, is logged and shown to the patient.

Every decision is written to AccessLog, including denials.
"""
import datetime

from django.utils import timezone

from .decorators import get_role
from .models import AccessLog, Appointment, ConsentGrant, Patient

SCOPES = tuple(s for s, _ in ConsentGrant.SCOPE_CHOICES)
BREAK_GLASS_HOURS = 24
TREATMENT_STATUSES = ('Scheduled', 'Completed')


def active_grants(patient, grantee=None, scope=None):
    now = timezone.now()
    qs = ConsentGrant.objects.filter(patient=patient, revoked_at__isnull=True).exclude(expires_at__lte=now)
    if grantee is not None:
        qs = qs.filter(grantee=grantee)
    if scope is not None:
        qs = qs.filter(scope=scope)
    return qs


def access_basis(user, patient, scope):
    """Return why `user` may access `scope` of `patient`, or None."""
    role = get_role(user)
    if role == 'patient':
        return 'self' if user.patient.pk == patient.pk else None
    if role == 'doctor' and Appointment.objects.filter(
            patient=patient, doctor__user=user, status__in=TREATMENT_STATUSES).exists():
        return 'treatment'
    grant = active_grants(patient, user, scope).first()
    if grant:
        return 'break_glass' if grant.source == ConsentGrant.SOURCE_BREAK_GLASS else 'grant'
    return None


def check_access(user, patient, scope, action):
    """Decide and log. Returns True when allowed."""
    basis = access_basis(user, patient, scope)
    AccessLog.objects.create(
        actor=user, actor_role=get_role(user) or '', patient=patient, scope=scope,
        action=action, allowed=basis is not None, basis=basis or 'none',
    )
    return basis is not None


def grant(patient, grantee, scopes, days=None, source=ConsentGrant.SOURCE_PATIENT, reason=''):
    expires = timezone.now() + datetime.timedelta(days=days) if days else None
    created = []
    for scope in scopes:
        if scope not in SCOPES:
            continue
        existing = active_grants(patient, grantee, scope).first()
        if existing:
            if expires != existing.expires_at or source != existing.source:
                existing.expires_at, existing.source = expires, source
                existing.save(update_fields=['expires_at', 'source'])
            created.append(existing)
            continue
        created.append(ConsentGrant.objects.create(
            patient=patient, grantee=grantee, scope=scope, source=source, reason=reason[:255], expires_at=expires))
    return created


def break_glass(doctor_user, patient, reason):
    reason = (reason or '').strip()
    if len(reason) < 10:
        raise ValueError("Please give a reason (at least 10 characters).")
    grants = grant(patient, doctor_user, SCOPES, days=None, source=ConsentGrant.SOURCE_BREAK_GLASS, reason=reason)
    expires = timezone.now() + datetime.timedelta(hours=BREAK_GLASS_HOURS)
    for g in grants:
        g.expires_at = expires
        g.save(update_fields=['expires_at'])
    AccessLog.objects.create(actor=doctor_user, actor_role='doctor', patient=patient, scope='all',
                             action='break_glass', allowed=True, basis='break_glass')
    return grants


def revoke(grant_obj):
    if grant_obj.revoked_at is None:
        grant_obj.revoked_at = timezone.now()
        grant_obj.save(update_fields=['revoked_at'])


def patients_visible_to(user, scope):
    """Patient ids this user may see for `scope` (used to filter lists such as the lab dashboard)."""
    ids = set(active_grants_for_user(user, scope).values_list('patient_id', flat=True))
    if get_role(user) == 'doctor':
        ids |= set(Appointment.objects.filter(doctor__user=user, status__in=TREATMENT_STATUSES)
                   .values_list('patient_id', flat=True))
    return ids


def active_grants_for_user(user, scope):
    now = timezone.now()
    return ConsentGrant.objects.filter(grantee=user, scope=scope, revoked_at__isnull=True).exclude(expires_at__lte=now)
