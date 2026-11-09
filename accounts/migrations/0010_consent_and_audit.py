# Adds patient consent grants and the access log.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0009_doctor_schedule_appointment'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsentGrant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(choices=[('records', 'Medical history'), ('prescriptions', 'Prescriptions'), ('tests', 'Lab tests')], max_length=20)),
                ('source', models.CharField(default='patient', max_length=20)),
                ('reason', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('grantee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consent_received', to=settings.AUTH_USER_MODEL)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consent_grants', to='accounts.patient')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actor_role', models.CharField(blank=True, max_length=20)),
                ('scope', models.CharField(max_length=20)),
                ('action', models.CharField(max_length=40)),
                ('allowed', models.BooleanField()),
                ('basis', models.CharField(blank=True, max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_log_entries', to=settings.AUTH_USER_MODEL)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_log', to='accounts.patient')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='consentgrant',
            index=models.Index(fields=['patient', 'grantee', 'scope'], name='accounts_co_patient_b0b553_idx'),
        ),
    ]
