from django import forms
from .models import User, Grade, Subject

TW = (
    'w-full px-4 py-2.5 border border-gray-300 rounded-md '
    'focus:outline-none focus:ring-2 focus:ring-blue-500 '
    'focus:border-blue-500 text-sm'
)


# Basic login form
class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': TW, 'placeholder': 'Username',
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': TW, 'placeholder': 'Password',
    }))



# Base form for creating new users
class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': TW,
    }))

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name',
            'email', 'role', 'school', 'phone',
        ]
        widgets = {
            'username':   forms.TextInput(attrs={'class': TW}),
            'first_name': forms.TextInput(attrs={'class': TW}),
            'last_name':  forms.TextInput(attrs={'class': TW}),
            'email':      forms.EmailInput(attrs={'class': TW}),
            'role':       forms.Select(attrs={'class': TW}),
            'school':     forms.Select(attrs={'class': TW}),
            'phone':      forms.TextInput(attrs={'class': TW}),
        }



# Filters attendance
class AttendanceFilterForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.Select(attrs={'class': TW}),
    )
    date = forms.DateField(widget=forms.DateInput(attrs={
        'type': 'date', 'class': TW,
    }))



# Inputting grades, from teacher end
class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = [
            'learner', 'subject', 'assessment_name',
            'score', 'max_score', 'date', 'notes',
        ]
        widgets = {
            'learner':         forms.Select(attrs={'class': TW}),
            'subject':         forms.Select(attrs={'class': TW}),
            'assessment_name': forms.TextInput(attrs={'class': TW}),
            'score':           forms.NumberInput(attrs={'class': TW}),
            'max_score':       forms.NumberInput(attrs={'class': TW}),
            'date':            forms.DateInput(attrs={
                'type': 'date', 'class': TW,
            }),
            'notes': forms.Textarea(attrs={
                'class': TW, 'rows': 3,
            }),
        }

class ReportCardUploadForm(forms.From):
    #Upload a photo of a learner's report card for Ollama grade extraction
    learner = forms.ModelChoiceField(
        queryset=User.objects.filter(role='learner').order_by('last_name'),
        widget=froms.Select(attrs={
            'class': TW,
            'accept': 'image/*',
        }),
        help_text='Upload a clear photo of the report card.',
    )