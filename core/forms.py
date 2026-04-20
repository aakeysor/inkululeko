from django import forms
from .models import User, Grade, Subject, School

TW = (
    'w-full px-4 py-2.5 border border-gray-300 rounded-md '
    'focus:outline-none focus:ring-2 focus:ring-blue-500 '
    'focus:border-blue-500 text-sm'
)


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': TW, 'placeholder': 'Username',
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': TW, 'placeholder': 'Password',
    }))


class BaseUserCreateForm(forms.ModelForm):
    """Base form with fields shared across all roles."""
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': TW,
    }))

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'role', 'school', 'phone', 'date_of_birth', 'address',
            'emergency_contact_name', 'emergency_contact_phone',
        ]
        widgets = {
            'username':                forms.TextInput(attrs={'class': TW}),
            'first_name':              forms.TextInput(attrs={'class': TW}),
            'last_name':               forms.TextInput(attrs={'class': TW}),
            'email':                   forms.EmailInput(attrs={'class': TW}),
            'role':                    forms.Select(attrs={'class': TW}),
            'school':                  forms.Select(attrs={'class': TW}),
            'phone':                   forms.TextInput(attrs={'class': TW}),
            'date_of_birth':           forms.DateInput(attrs={'type': 'date', 'class': TW}),
            'address':                 forms.TextInput(attrs={'class': TW}),
            'emergency_contact_name':  forms.TextInput(attrs={'class': TW}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': TW}),
        }


class LearnerCreateForm(BaseUserCreateForm):
    class Meta(BaseUserCreateForm.Meta):
        fields = BaseUserCreateForm.Meta.fields + [
            'grade_level', 'parent_guardian_name', 'parent_guardian_phone',
        ]
        widgets = {
            **BaseUserCreateForm.Meta.widgets,
            'grade_level':             forms.TextInput(attrs={'class': TW}),
            'parent_guardian_name':     forms.TextInput(attrs={'class': TW}),
            'parent_guardian_phone':    forms.TextInput(attrs={'class': TW}),
        }


class AssistantCreateForm(BaseUserCreateForm):
    class Meta(BaseUserCreateForm.Meta):
        fields = BaseUserCreateForm.Meta.fields + [
            'subject_taught', 'grade_levels_taught', 'experience_years',
            'qualifications', 'certifications', 'specializations',
        ]
        widgets = {
            **BaseUserCreateForm.Meta.widgets,
            'subject_taught':      forms.TextInput(attrs={'class': TW}),
            'grade_levels_taught': forms.TextInput(attrs={'class': TW}),
            'experience_years':    forms.NumberInput(attrs={'class': TW}),
            'qualifications':      forms.Textarea(attrs={'class': TW, 'rows': 2}),
            'certifications':      forms.Textarea(attrs={'class': TW, 'rows': 2}),
            'specializations':     forms.Textarea(attrs={'class': TW, 'rows': 2}),
        }


class MentorCreateForm(BaseUserCreateForm):
    class Meta(BaseUserCreateForm.Meta):
        fields = BaseUserCreateForm.Meta.fields + [
            'organization', 'focus_areas', 'background', 'availability',
        ]
        widgets = {
            **BaseUserCreateForm.Meta.widgets,
            'organization': forms.TextInput(attrs={'class': TW}),
            'focus_areas':  forms.TextInput(attrs={'class': TW}),
            'background':   forms.TextInput(attrs={'class': TW}),
            'availability': forms.TextInput(attrs={'class': TW}),
        }


class AdminCreateForm(BaseUserCreateForm):
    """Admin form — just the base fields."""
    pass


# Keep this alias for backward compatibility
UserCreateForm = BaseUserCreateForm


class AttendanceFilterForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': TW}),
    )
    date = forms.DateField(widget=forms.DateInput(attrs={
        'type': 'date', 'class': TW,
    }))


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
            'date':            forms.DateInput(attrs={'type': 'date', 'class': TW}),
            'notes':           forms.Textarea(attrs={'class': TW, 'rows': 3}),
        }


class ReportCardUploadForm(forms.Form):
    learner = forms.ModelChoiceField(
        queryset=User.objects.filter(role='learner').order_by('last_name'),
        widget=forms.Select(attrs={'class': TW}),
    )
    image = forms.ImageField(
        widget=forms.FileInput(attrs={'class': TW, 'accept': 'image/*'}),
        help_text='Upload a clear photo of the report card.',
    )


class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ['name', 'location']
        widgets = {
            'name':     forms.TextInput(attrs={'class': TW}),
            'location': forms.TextInput(attrs={'class': TW}),
        }