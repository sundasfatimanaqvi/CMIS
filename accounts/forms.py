from django import forms
from django.contrib.auth.models import User

ROLE_CHOICES = [
    ('patient', 'Patient'),
    ('doctor', 'Doctor'),
    ('laboratory', 'Laboratory'),
    ('pharmacy', 'Pharmacy'),
]

class RegistrationForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=ROLE_CHOICES, 
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Password"
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirm Password"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'role']

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        
        return cleaned_data
    

from django import forms
from .models import Prescription, Doctor

class PrescribeMedicineForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(queryset=User.objects.filter(is_staff=True), widget=forms.Select(attrs={'class': 'form-control'})) 

    class Meta:
        model = Prescription
        fields = ['doctor', 'medicine_name', 'dosage', 'instructions']
        widgets = {
            'medicine_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter medicine name'}),
            'dosage': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter dosage'}),
            'instructions': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter instructions', 'rows': 3}),
        }


from .models import MedicalTest, MedicalHistory


class PrescribeTestForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.all(), 
        required=False,  # Optional doctor field
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = MedicalTest
        fields = ['doctor', 'test_name']
        widgets = {
            'test_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter test name'}),
        }

from django import forms
from .models import MedicalHistory

class MedicalHistoryForm(forms.ModelForm):
    class Meta:
        model = MedicalHistory
        fields = ['details', 'doctor']  # Doctor field added
        widgets = {
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter medical history details'}),
            'doctor': forms.HiddenInput()  # Hide doctor field in the form
        }
