#
#  forms.py
# AntNupTracker Server, backend for recording and managing ant nuptial flight data
# Copyright (C) 2020  Abouheif Lab
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

from django import forms
from django.contrib.auth.forms import (
    UserCreationForm as BaseUserForm,
    PasswordResetForm as BasePasswordReset,
)
from django.contrib.auth.models import User
from .models import FlightUser, Role


class UserCreationForm(BaseUserForm):
    email = forms.EmailField(
        max_length=128,
        help_text="Enter a valid email address. We need this to verify your account.",
    )

    ROLE_CHOICES = [
        ("enthusiast", "Citizen Scientist"),
        ("myrmecologist", "Professional Myrmecologist"),
    ]

    professional = forms.ChoiceField(
        label="Role in the Ant Community",
        help_text="Enter your role in the ant community.",
        choices=ROLE_CHOICES,
    )
    institution = forms.CharField(
        label="Institution or Affiliation",
        max_length=80,
        required=False,
        help_text="Enter your institution or affiliation.",
    )
    description = forms.CharField(
        label="Say a few words about yourself (optional)",
        required=False,
        help_text="This will be visible on your public profile.",
        widget=forms.Textarea,
    )

    def clean_professional(self):
        # print(self.cleaned_data)

        stringValue = self.cleaned_data["professional"]
        if stringValue == "myrmecologist":
            return True
        else:
            return False

    class Meta:
        model = User
        fields = (
            "username",
            "password1",
            "password2",
            "email",
            "professional",
            "institution",
            "description",
        )


# Password reset based on https://medium.com/@renjithsraj/how-to-reset-password-in-django-bd5e1d6ed652 by Renjith S Raj
class PasswordResetForm(BasePasswordReset):

    class Meta:
        model = User
        fields = "email"


class PasswordChangeForm(BaseUserForm):

    class Meta:
        model = User
        fields = ("password1", "password2")

DeleteUserForm = PasswordResetForm


class DeleteUserConfirmationForm(forms.Form):
    accept_deletion = forms.BooleanField(
        required=True, label="Confirm account deletion"
    )
