from django.core.management.base import BaseCommand

from accounts import consent
from accounts.models import Doctor, Laboratory, Patient, Pharmacy


class Command(BaseCommand):
    help = ("One-off helper for demos and for data that existed before consent was added: "
            "every patient shares every scope with every doctor, pharmacy and laboratory. "
            "Do NOT run this on real patient data.")

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='confirm that this is demo data')

    def handle(self, *args, **options):
        if not options['yes']:
            self.stderr.write("Refusing to run without --yes. This gives everyone access to everything.")
            return
        grantees = [p.user for model in (Doctor, Pharmacy, Laboratory) for p in model.objects.select_related('user')]
        count = 0
        for patient in Patient.objects.all():
            for user in grantees:
                count += len(consent.grant(patient, user, consent.SCOPES))
        self.stdout.write(self.style.SUCCESS(f"Done. {count} grants active."))
