"""Role based access helpers."""
from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib.auth.views import redirect_to_login

ROLES = ('doctor', 'patient', 'pharmacy', 'laboratory')


def get_role(user):
    """Return the user's role name (the related profile attribute) or None."""
    if not user.is_authenticated:
        return None
    for role in ROLES:
        if hasattr(user, role):
            return role
    return None


def role_required(role, api=False):
    """Allow only logged-in users who have the given role profile.

    With ``api=True`` failures are returned as JSON (401/403) instead of redirects,
    which is what the fetch() based endpoints expect.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if api:
                    return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=401)
                return redirect_to_login(request.get_full_path())
            if get_role(request.user) != role:
                if api:
                    return JsonResponse({'success': False, 'error': f'Only {role}s can do this.'}, status=403)
                messages.error(request, f'That page is only available to {role} accounts.')
                return redirect('dashboard')
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


doctor_required = role_required('doctor')
patient_required = role_required('patient')
pharmacy_required = role_required('pharmacy')
laboratory_required = role_required('laboratory')
