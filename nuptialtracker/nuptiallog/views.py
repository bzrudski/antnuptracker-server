#
# views.py
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

# import io
# import json
import os
from threading import Thread

from PIL import Image
from django.contrib.auth.models import User
from django.contrib.gis.db.models.functions import Distance
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views import generic
from knox.auth import TokenAuthentication
from knox.views import LoginView as KnoxLoginView
from nuptialtracker.settings import MEDIA_ROOT
from rest_framework import filters
from rest_framework import generics
from rest_framework import mixins
from rest_framework import status
from rest_framework import viewsets
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import BadLocationUrlException
from . import forms

# from django_filters.rest_framework import DjangoFilterBackend
from . import models
from . import notifications

# from .faq import getFaqs
from .parsers import ImageUploadParser

# from .permissions import IsOwnerOrReadOnly, IsOwner, IsProfessional, IsProfessionalOrReadOnly, IsAuthor, IsAuthorOrReadOnly
from . import permissions
from . import serializers
from .taxonomy import SPECIES
from . import tokens
from .weather import get_weather_for_flight


# from django.contrib.auth import login, authenticate
# import sys


# Create your views here.
class GenusListView(APIView):
    def get(self, request, *args, **kwargs):
        serializer = serializers.NewGenusSerializer(
            serializers.Genus.objects.all(), many=True
        )
        # return Response({"genera":GENERA}, status=status.HTTP_200_OK)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GenusViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = serializers.Genus.objects.all()
    serializer_class = serializers.NewGenusSerializer
    # permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        serializer = serializers.GenusNameIdSerializer(self.queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class SpeciesViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    # permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.NewSpeciesSerializer

    def get_queryset(self):
        return serializers.Species.objects.filter(genus__id=self.kwargs["genus_pk"])


class TaxonomyView(APIView):
    def get(self, request, *args, **kwargs):
        return Response(SPECIES, status=status.HTTP_200_OK)


class InvalidGenusException(Exception):
    pass


class SpeciesDetailView(APIView):
    def get_species_for_genus(self, genus):
        try:
            return SPECIES[genus.title()]
        except KeyError:
            description = "Genus " + genus + " does not exist"
            raise InvalidGenusException(description)

    def get(self, request, genus, format=None):
        try:
            speciesList = self.get_species_for_genus(genus)
            return Response({"species": speciesList}, status=status.HTTP_200_OK)
        except:
            return Response("Invalid genus", status=status.HTTP_404_NOT_FOUND)


class MyFlightsList(mixins.ListModelMixin, generics.GenericAPIView):
    serializer_class = serializers.FlightSerializerBarebones
    permission_classes = [permissions.permissions.IsAuthenticated]

    def get_queryset(self):
        return serializers.Flight.objects.all().filter(owner=self.request.user)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class MySpeciesList(mixins.ListModelMixin, generics.GenericAPIView):
    # serializer_class = SpeciesSerializer
    serializer_class = serializers.IdOnlySpeciesSerializer
    permission_classes = [permissions.permissions.IsAuthenticated]
    # pagination_class = BiggerPagesPaginator

    def get_queryset(self):
        return serializers.Species.objects.all().filter(
            flightuser=self.request.user.flightuser
        )

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = serializers.IdOnlySpeciesSerializer(data=request.data, many=True)

        # print("Preparing to update species list")

        if serializer.is_valid():
            # species = serializer.validated_data["species"]

            for species in serializer.validated_data:
                # print("Adding species: "+str(species))
                user.flightuser.species.add(species["id"])
                # print("Species added: "+str(species))

            new_serializer = serializers.IdOnlySpeciesSerializer(
                user.flightuser.species, many=True
            )

            return Response(new_serializer.data, status=status.HTTP_200_OK)
            # return Response("Species list modified", status=status.HTTP_200_OK)
        # print(serializer.errors)
        return Response("Bad request", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        user = request.user
        serializer = serializers.IdOnlySpeciesSerializer(data=request.data, many=True)

        if serializer.is_valid():
            # speciesList = serializer.validated_data["species"]

            for species in serializer.validated_data:
                # print("Removing species: "+str(species))
                user.flightuser.species.remove(species["id"])

            new_serializer = serializers.IdOnlySpeciesSerializer(
                user.flightuser.species, many=True
            )

            return Response(new_serializer.data, status=status.HTTP_200_OK)
            # return Response("Species list modified", status=status.HTTP_200_OK)
        # print(serializer.errors)
        return Response("Bad request", status=status.HTTP_400_BAD_REQUEST)


class MyGenusList(mixins.ListModelMixin, generics.GenericAPIView):
    # serializer_class = GenusSerializer
    serializer_class = serializers.IdOnlyGenusSerializer
    permission_classes = [permissions.permissions.IsAuthenticated]
    # pagination_class = BiggerPagesPaginator

    def get_queryset(self):
        return serializers.Genus.objects.all().filter(
            flightuser=self.request.user.flightuser
        )

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = request.user
        # print(request.data)
        serializer = serializers.IdOnlyGenusSerializer(data=request.data, many=True)

        # print(serializer.data)

        # print("Preparing to update genus list")

        if serializer.is_valid():
            # print(serializer.validated_data)

            # genera = serializer.validated_data["genera"]

            for genus in serializer.validated_data:
                # print("Adding genus: "+str(genus))
                user.flightuser.genera.add(genus["id"])
                # print("Genus added: "+str(genus))

            new_serializer = serializers.IdOnlyGenusSerializer(
                user.flightuser.genera, many=True
            )

            return Response(new_serializer.data, status=status.HTTP_200_OK)
            # return Response("Genus list modified", status=status.HTTP_200_OK)
        # print(serializer.errors)
        return Response("Bad request", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        user = request.user
        serializer = serializers.IdOnlyGenusSerializer(data=request.data, many=True)

        if serializer.is_valid():
            # genusList = serializer.validated_data["genera"]

            for genus in serializer.validated_data:
                # print("Removing genus: "+str(genus))
                user.flightuser.genera.remove(genus["id"])

            new_serializer = serializers.IdOnlyGenusSerializer(
                user.flightuser.genera, many=True
            )

            return Response(new_serializer.data, status=status.HTTP_200_OK)
        # print(serializer.errors)
        return Response("Bad request", status=status.HTTP_400_BAD_REQUEST)


class UpdateMySpeciesList(APIView):
    # serializer_class = SpeciesModificationSerializer
    permission_classes = [permissions.permissions.IsAuthenticated]

    queryset = serializers.Species.objects.all()

    def update(self, request):
        user = self.request.user
        toAdd = request.data["toAdd"]
        # toRemove = request.data["toRemove"]

        return Response(toAdd[0])
        # print(toRemove)

    def post(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class ImageView(APIView):
    permission_classes = [
        permissions.permissions.IsAuthenticated,
    ]
    authentication_classes = [TokenAuthentication]

    def get(self, request, filename):
        # print(filename)
        path = str(MEDIA_ROOT) + "/flight_pics/" + filename

        if os.path.exists(path):
            imageFile = open(path, "rb")
            image = imageFile.read()
            imageFile.close()
            return HttpResponse(image, content_type="image/png")

        else:
            return Response("No such image", status=status.HTTP_404_NOT_FOUND)


class ChangelogForFlight(mixins.ListModelMixin, generics.GenericAPIView):
    # queryset = Changelog.objects.all()
    serializer_class = serializers.ChangelogSerializer
    pagination_class = None
    permission_classes = [permissions.permissions.IsAuthenticated]
    lookup_field = "flightID"
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return (
            serializers.Changelog.objects.all()
            .filter(flight_id=self.kwargs["pk"])
            .order_by("-date")
        )

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class WeatherForFlight(mixins.RetrieveModelMixin, generics.GenericAPIView):
    serializer_class = serializers.WeatherSerializer
    lookup_field = "flight_id"
    lookup_url_kwarg = "pk"
    permission_classes = [permissions.permissions.IsAuthenticated]

    def get_object(self):
        queryset = self.get_queryset()
        filter = {"flight_id": self.kwargs["pk"]}

        weather = get_object_or_404(queryset, **filter)

        self.check_object_permissions(self.request, weather)
        return weather

    def get_queryset(self):
        try:
            return serializers.Weather.objects.all()
        except:
            return None

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class LoginView(KnoxLoginView):
    authentication_classes = [BasicAuthentication]
    alphanumerics = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890:_-"

    def get_user_serializer_class(self):
        return serializers.FlightUserSerializer

    def get_post_response_data(self, request, token, instance):
        UserSerializer = self.get_user_serializer_class()

        # print(request.data)

        deviceID = self.getDeviceID(request, instance)

        if not deviceID:
            deviceID = 0

        data = {
            "expiry": self.format_expiry_datetime(instance.expiry),
            "token": token,
            "deviceID": deviceID,
        }

        # if UserSerializer is not None:
        #     data.update(UserSerializer(
        #         request.user,
        #         context=self.get_context()
        #     ).data)

        user_info = serializers.FlightUserSerializer(
            request.user.flightuser, context=self.get_context()
        ).data
        data.update(user_info)

        data["user"] = user_info

        return data

    def getDeviceID(self, request, authToken) -> int:
        device = None
        deviceID = 0

        deviceID = self.request.META.get("HTTP_DEVICEID")
        platform = self.request.data.get("platform")
        model = self.request.data.get("model")
        deviceToken = self.request.data.get("deviceToken", "")

        # print("Logged in with token: {}".format(deviceToken))

        user = self.request.user
        lastLoggedIn = timezone.now().replace(microsecond=0)

        try:
            if not deviceID:
                raise Exception("No device id provided.")

            device = models.Device.objects.get(deviceID)
            # print("Using stored")

            if device.user != user:
                return None

            if device.platform != platform:
                return None

            if device.model != model:
                return None

            device.deviceToken = deviceToken
            device.lastLoggedIn = lastLoggedIn
            device.authToken = authToken
            device.save()

            # print("Retrieved device from storage...")
            # print(f"Device ID is now {deviceID}")
            return device.deviceID

        except:

            try:
                # print("Looking in existing tokens")

                if deviceToken == "":
                    raise Exception("No device token")

                for c in deviceToken:
                    if not (c in LoginView.alphanumerics):
                        deviceToken = None
                        raise Exception("Illegal token")

                device = models.Device.objects.get(deviceToken=deviceToken)
                # deviceID = device.deviceID
                # print("Found device by token")
                # print(f"Device ID is now {deviceID}")

                if device.model != model:
                    raise Exception("Wrong model")

                if device.platform != platform:
                    raise Exception("Wrong platform")

                if device.user != user:
                    device.user = user
                    device.save()

                device.lastLoggedIn = timezone.now().replace(microsecond=0)
                device.authToken = authToken
                device.save()

                return device.deviceID

            except:
                deviceID = models.Device.generate_new_id()
                # print("Create new.")
                # print(f"Device ID is now {deviceID}")
                device = models.Device.objects.create(
                    deviceID=deviceID,
                    model=model,
                    platform=platform,
                    authToken=authToken,
                    deviceToken=deviceToken,
                    lastLoggedIn=lastLoggedIn,
                    user=self.request.user,
                )
                device.save()

                # print("The device token is {}".format(device.deviceToken))

                return device.deviceID

        # finally:
        #     print(deviceID, end='\n')
        #     #if (not deviceID == None):
        #     # device.authToken = authToken
        #     # device.save()
        #     return deviceID


class VerifyTokenView(APIView):

    def get(self, request, format=None):
        return Response(status=status.HTTP_200_OK)

    def post(self, request, format=None):
        # auth = self.request.auth
        if self.request.auth != None:
            # print("Authenticated request.")
            # user = self.request.user.flightuser
            # role = user.role.role
            # deviceID = self.request.META['HTTP_DEVICEID']
            # print("Got request {}".format(self.request.data))
            device_id = self.request.data.get("deviceID")
            device_token = self.request.data.get("deviceToken")

            if device_id is None:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

            try:
                device = models.Device.objects.get(deviceID=device_id)

                device.lastLoggedIn = timezone.now()
                device.active = True
                device.deviceToken = device_token if device_token != None else ""
                device.save()

                user = self.request.user.flightuser

                serializer = serializers.FlightUserSerializer(user)

                return Response(serializer.data, status=status.HTTP_200_OK)
            except:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        return Response(status=status.HTTP_401_UNAUTHORIZED)


class CreateUserForm(generic.FormView):
    # In part based on code from
    # # https://medium.com/@frfahim/django-registration-with-confirmation-email-bb5da011e4ef
    # by Farhadur Reja Fahim
    form_template = "nuptiallog/AccountCreateForm.html"
    email_successful = "nuptiallog/EmailSent.html"
    email_failed = "nuptiallog/EmailFailed.html"

    def post(self, request, *args, **kwargs):
        form = forms.UserCreationForm(request.POST)
        if form.is_valid():
            email_addr = form.cleaned_data["email"]

            if len(User.objects.all().filter(email=email_addr)) != 0:
                form.errors.update(
                    {"email": ["A user with that email address already exists"]}
                )
                return render(request, self.form_template, {"form": form})

            professional = form.cleaned_data["professional"]
            institution = form.cleaned_data["institution"]

            username = form.cleaned_data["username"]

            if len(username) < 6:
                form.errors.update({"username": ["Please enter a longer username"]})
                return render(request, self.form_template, {"form": form})

            if professional and not institution:
                form.errors.update({"institution": ["You must enter your institution"]})
                return render(request, self.form_template, {"form": form})

            user = form.save(commit=False)
            user.is_active = False
            # user.username = user.username.lower()
            user.save()
            user.flightuser.professional = professional
            user.flightuser.institution = institution
            user.flightuser.description = form.cleaned_data["description"]

            # role = Role.objects.get(pk=form.cleaned_data["role"])
            user.save()
            user.flightuser.save()
            # print("User saved")
            current_site = get_current_site(request)
            subject = "Activate NuptialTracker Account"
            message = render_to_string(
                "nuptiallog/ActivateEmail.html",
                {
                    "user": user,
                    "domain": current_site.domain,
                    "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": tokens.accountActivationToken.make_token(user),
                },
            )
            to_email = form.cleaned_data.get("email")
            email = EmailMessage(subject, message, to=[to_email])
            email.content_subtype = "html"
            # print("Preparing to send email.")
            try:
                email.send()

                # print("Sent email")
                return render(
                    request,
                    "nuptiallog/EmailSent.html",
                    {"user": user},
                    status=status.HTTP_201_CREATED,
                )
            except:
                # print("Error sending email.")
                return render(request, self.email_failed, {"user": user}, status=400)
        else:
            return render(request, self.form_template, {"form": form})

    def get(self, request, *args, **kwargs):
        form = forms.UserCreationForm()
        return render(request, self.form_template, {"form": form})


# Password reset based on https://medium.com/@renjithsraj/how-to-reset-password-in-django-bd5e1d6ed652 by Renjith S Raj


class ResetPasswordForm(generic.FormView):
    mobile = False
    form_template = "nuptiallog/PasswordResetForm.html"
    email_successful = "nuptiallog/EmailSentPassChange.html"

    def post(self, request, *args, **kwargs):
        form = forms.PasswordResetForm(request.POST)
        if form.is_valid():
            to_email = form.cleaned_data.get("email")

            try:
                user = User.objects.get(email=to_email)

                current_site = get_current_site(request)
                subject = "Reset NuptialTracker Password"
                message = render_to_string(
                    "nuptiallog/PasswordResetEmail.html",
                    {
                        "user": user,
                        "domain": current_site.domain,
                        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                        "token": tokens.passwordResetToken.make_token(user),
                    },
                )
                email = EmailMessage(subject, message, to=[to_email])
                email.content_subtype = "html"
                # print("Preparing to send email.")
                email.send()
            except:
                user = None
            finally:
                # print("Sent email")
                return render(
                    request,
                    self.email_successful,
                    {"email": to_email, "mobile": self.mobile},
                    status=status.HTTP_201_CREATED,
                )
        else:
            return render(
                request, self.form_template, {"form": form, "mobile": self.mobile}
            )

    def get(self, request, *args, **kwargs):
        form = forms.PasswordResetForm()
        return render(
            request, self.form_template, {"form": form, "mobile": self.mobile}
        )


class UserActivationView(generic.View):
    def activate(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except:
            user = None

        if user is not None and tokens.accountActivationToken.check_token(user, token):
            user.is_active = True
            user.save()
            return render(request, "nuptiallog/SuccessActivation.html", {"user": user})
        else:
            return render(
                request,
                "nuptiallog/FailureActivation.html",
                status=status.HTTP_404_NOT_FOUND,
            )

    def get(self, request, uidb64, token):
        return self.activate(request, uidb64, token)


class ChangePasswordForm(generic.FormView):
    def getUser(self, uidb64):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except:
            user = None

        return user

    def get(self, request, uidb64, token):

        user = self.getUser(uidb64)

        if user is not None and tokens.passwordResetToken.check_token(user, token):
            form = forms.PasswordChangeForm()
            return render(
                request, "nuptiallog/PassChangeForm.html", {"form": form, "user": user}
            )
        return render(
            request,
            "nuptiallog/FailurePassChange.html",
            status=status.HTTP_404_NOT_FOUND,
        )

    def post(self, request, uidb64, token):
        user = self.getUser(uidb64)

        if user is not None and tokens.passwordResetToken.check_token(user, token):
            form = forms.PasswordChangeForm(request.POST)
            if form.is_valid():
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=uid)
                # print(user)
                user.set_password(form.cleaned_data["password1"])
                user.save()
                return render(
                    request, "nuptiallog/SuccessPassChange.html", {"user": user}
                )
            else:
                return render(
                    request,
                    "nuptiallog/PassChangeForm.html",
                    {"form": form, "user": user},
                )
        else:
            return render(
                request,
                "nuptiallog/FailurePassChange.html",
                status=status.HTTP_404_NOT_FOUND,
            )


class DeleteUserFormView(generic.FormView):
    mobile = False
    form_template = "nuptiallog/DeleteUserForm.html"
    email_successful = "nuptiallog/DeleteUserEmailSent.html"

    def post(self, request, *args, **kwargs):
        form = forms.DeleteUserForm(request.POST)
        if form.is_valid():
            to_email = form.cleaned_data.get("email")

            try:
                user = User.objects.get(email=to_email)

                current_site = get_current_site(request)
                subject = "Delete AntNupTracker User"
                message = render_to_string(
                    "nuptiallog/DeleteUserEmail.html",
                    {
                        "user": user,
                        "domain": current_site.domain,
                        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                        "token": tokens.deleteAccountToken.make_token(user),
                    },
                )
                email = EmailMessage(subject, message, to=[to_email])
                email.content_subtype = "html"
                # print("Preparing to send email.")
                email.send()
            except:
                user = None
            finally:
                # print("Sent email")
                return render(
                    request,
                    self.email_successful,
                    {"email": to_email, "mobile": self.mobile},
                    status=status.HTTP_201_CREATED,
                )
        else:
            return render(
                request, self.form_template, {"form": form, "mobile": self.mobile}
            )

    def get(self, request, *args, **kwargs):
        form = forms.DeleteUserForm()
        return render(
            request, self.form_template, {"form": form, "mobile": self.mobile}
        )


class ConfirmDeleteUserView(generic.FormView):
    def getUser(self, uidb64):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except:
            user = None

        return user

    def get(self, request, uidb64, token):

        user = self.getUser(uidb64)

        if user is not None and tokens.deleteAccountToken.check_token(user, token):
            form = forms.DeleteUserConfirmationForm()
            return render(
                request, "nuptiallog/DeleteUserConfirm.html", {"form": form, "user": user}
            )
        return render(
            request,
            "nuptiallog/DeleteUserFailure.html",
            status=status.HTTP_404_NOT_FOUND,
        )

    def post(self, request, uidb64, token):
        user = self.getUser(uidb64)

        print(f"Got user: {user}")

        if user is not None and tokens.deleteAccountToken.check_token(user, token):
            form = forms.DeleteUserConfirmationForm(request.POST)
            if form.is_valid():
                # print("Deletion form is valid!")
                uid = force_str(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=uid)

                # print(f"Got user {user} to delete!")
                # print(user)

                if not form.cleaned_data["accept_deletion"]:
                    return render(
                        request,
                        "nuptiallog/DeleteUserConfirm.html",
                        {"form": form, "user": user},
                    )

                # print("Preparing to delete flights.")
                user.flights.all().delete()
                # print("Preparing to delete flight user.")
                user.flightuser.delete()
                # print("Preparing to delete user.")
                user.delete()

                return render(
                    request, "nuptiallog/DeleteUserSuccess.html", {"user": user}
                )
            else:
                print(form.errors)
                return render(
                    request,
                    "nuptiallog/DeleteUserConfirm.html",
                    {"form": form, "user": user},
                )
        else:
            return render(
                request,
                "nuptiallog/DeleteUserFailure.html",
                status=status.HTTP_404_NOT_FOUND,
            )


class UserDetailView(mixins.RetrieveModelMixin, generics.GenericAPIView):
    serializer_class = serializers.FlightUserSerializer
    lookup_field = "user__username"
    lookup_url_kwarg = "username"
    permission_classes = [permissions.IsUserOrAuthenticatedReadOnly]
    authentication_classes = [TokenAuthentication]

    def get_queryset(self):
        return serializers.FlightUser.objects.all()

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        serializer = serializers.FlightUserSerializer(data=self.request.data)

        if not serializer.is_valid():
            return Response(status=status.HTTP_400_BAD_REQUEST)

        flightuser = self.get_object()
        # flightuser = self.request.user.flightuser
        instance = serializer.update(flightuser, serializer.validated_data)

        return Response(serializer.data, status=status.HTTP_200_OK)


class FlightListNested(APIView):
    serializer_class = serializers.FlightSerializerFull
    renderer_classes = [JSONRenderer]
    permission_classes = [permissions.permissions.IsAuthenticated]
    authentication_classes = [BasicAuthentication]

    def get_data(self):
        flights = serializers.Flight.objects.all()
        serializer = serializers.FlightSerializerFull(flights, many=True)
        return serializer.data

    def get(self, request, *args, **kwargs):
        return Response(self.get_data(), status=status.HTTP_200_OK)


class ScientistImageView(APIView):
    def get(self, request, filename):
        # print(filename)
        path = str(MEDIA_ROOT) + "/scientist_pics/" + filename

        if os.path.exists(path):
            imageFile = open(path, "rb")
            image = imageFile.read()
            imageFile.close()
            return HttpResponse(image, content_type="image/png")

        else:
            return Response("No such image", status=status.HTTP_404_NOT_FOUND)


class FlightViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    """
    Viewsets to make management of flights simpler. This viewset assumes that a different
    serializer class is used for listing the flights and for creating them.
    """

    pagination_class = None
    filter_backends = [filters.OrderingFilter]
    serializer_class = serializers.FlightSerializer
    ordering_fields = ["flightID", "dateOfFlight", "dateRecorded"]
    ordering = ["-flightID"]

    # queryset = Flight.objects.all()

    # def get_serializer_class(self):
    #     if self.action == "list":
    #         return SimpleFlightSerializer
    #     # return super().get_serializer_class()
    #     return FlightSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.permissions.IsAuthenticated()]

        if self.action == "verify":
            return [permissions.IsProfessionalOrReadOnly()]

        return [permissions.IsOwnerOrReadOnly()]

    def get_queryset(self):
        queryset = serializers.Flight.objects.all()

        max_date = self.request.query_params.get("max_date")
        min_date = self.request.query_params.get("min_date")

        genus = self.request.query_params.get("genus")
        species = self.request.query_params.get("species")

        taxonomy_raw: str = self.request.query_params.get("taxonomy")

        location = self.request.query_params.get("loc")

        user_role = self.request.query_params.get("user_role")

        verified = self.request.query_params.get("verified")

        has_images = self.request.query_params.get("has_images")

        # max_distance = self.request.query_params.get("within")

        user = self.request.query_params.get("user")

        ordering = self.request.query_params.get("ordering")

        if taxonomy_raw != None:
            taxonomy_list = taxonomy_raw.split(",")
            # taxonomy_list = [entry.replace('+', ' ') for entry in taxonomy_list]
            taxonomy_list = [entry.split(" ", maxsplit=1) for entry in taxonomy_list]

            genera = [entry[0] for entry in taxonomy_list if len(entry) == 1]
            species_list = [
                serializers.Species.objects.get(genus__name=entry[0], name=entry[1])
                for entry in taxonomy_list
                if len(entry) > 1
            ]

            # print(genera)
            # print(species_list)

            queryset = queryset.filter(
                Q(genus__name__in=genera) | Q(species__in=species_list)
            )
            # queryset = queryset.filter(species__in=species_list)

        if user != None:
            queryset = queryset.filter(owner__username=user)

        if max_date != None:
            queryset = queryset.filter(dateOfFlight__lte=max_date)

        if min_date != None:
            queryset = queryset.filter(dateOfFlight__gte=min_date)

        # if (genus != None):
        #     queryset = queryset.filter(genus__name=genus)

        #     if (species != None):
        #         queryset = queryset.filter(species__name=species)

        if user_role != None:
            if user_role == "professional":
                queryset = queryset.filter(
                    owner__flightuser__professional=True,
                    owner__flightuser__flagged=False,
                )
            elif user_role == "enthusiast":
                queryset = queryset.filter(
                    owner__flightuser__professional=False,
                    owner__flightuser__flagged=False,
                )

        if verified != None:
            if verified == "true":
                queryset = queryset.filter(
                    Q(owner__flightuser__professional=True)
                    & Q(owner__flightuser__flagged=False)
                    | Q(validatedBy__isnull=False)
                )
            elif verified == "false":
                queryset = queryset.exclude(
                    Q(owner__flightuser__professional=True)
                    | Q(validatedBy__isnull=False)
                )

        if has_images != None:
            queryset = queryset.annotate(Count("images"))

            if has_images == "true":
                queryset = queryset.exclude(images__count=0)
            elif has_images == "false":
                queryset = queryset.filter(images__count=0)

        if ordering == None:
            return queryset

        # if (ordering in ["lastUpdated", "-lastUpdated"]):
        #     queryset = queryset.annotate(lastUpdated=F("changes"))

        if location != None and ordering.lower() in ["location", "-location"]:
            location_split = location.split(",")
            try:
                latitude = float(location_split[0])
                longitude = float(location_split[1])

                reference_point = serializers.Point(x=longitude, y=latitude, srid=4326)

                queryset = queryset.annotate(
                    distance=Distance("location", reference_point, spheroid=True)
                )

                if ordering.lower() == "location":
                    queryset = queryset.order_by("distance")
                else:
                    queryset = queryset.order_by("-distance")

                # if (max_distance != None):
                #     try:
                #         max_distance_float = float(max_distance)
                #         queryset = queryset.filter(location__distance_lte=(reference_point, D(max_distance_float)))
                #     except ValueError:
                #         pass

                # for f in queryset:
                #     print("Flight {}: Distance is {}".format(f.flightID, f.distance))

                return queryset

            except ValueError:
                pass

        if ordering.lower() in ["location", "-location"]:
            raise BadLocationUrlException

        queryset = filters.OrderingFilter().filter_queryset(
            self.request, queryset, self
        )
        return queryset

    def generate_notification_body_creation(self, flight):
        return f"A new {flight.genus.name} {flight.species.name} flight (id {flight.flightID}) has been recorded by {flight.owner.username}."

    def notify_users_flight_creation(self, flight):
        body = self.generate_notification_body_creation(flight)
        species = flight.species
        species_users = species.flightuser_set.all()
        genus = flight.genus
        genus_users = genus.flightuser_set.all()
        species_devices = (
            models.Device.objects.filter(user__flightuser__in=species_users)
            .exclude(deviceToken="")
            .exclude(authToken=None)
            .exclude(authToken__expiry__lte=timezone.now())
            .exclude(user=flight.owner)
            .values_list("deviceToken", flat=True)
        )
        genus_devices = (
            models.Device.objects.filter(user__flightuser__in=genus_users)
            .exclude(deviceToken="")
            .exclude(authToken=None)
            .exclude(authToken__expiry__lte=timezone.now())
            .exclude(user=flight.owner)
            .values_list("deviceToken", flat=True)
        )

        devices = genus_devices.union(species_devices)

        title = "Flight Created"

        # sendAllNotifications("Flight Created", body, devices, flightID=flight.flightID)
        notifications.send_notifications(devices=devices, title=title, body=body)

    def list(self, request, format=None):
        queryset = self.get_queryset()
        # sorted_queryset = filters.OrderingFilter().filter_queryset(request, queryset, self)
        serializer = serializers.SimpleFlightSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, format=None):
        serializer = serializers.FlightSerializerBarebones(data=self.request.data)

        # print("Serializer for new flight:")
        # print(serializer)

        user = self.request.user
        date = timezone.now().replace(microsecond=0)

        if not serializer.is_valid():
            return Response(
                {"error": "Invalid formatting"}, status=status.HTTP_400_BAD_REQUEST
            )

        # print("Validated Data:")
        # print(serializer.validated_data)

        location = serializers.Point(
            x=serializer.validated_data["location"]["x"],
            y=serializer.validated_data["location"]["y"],
            srid=4326,
        )

        # print(serializer.validated_data)
        # genusName = serializer.validated_data["genus"]["name"]
        # genus = Genus.objects.get(name=genusName)
        # genusName = serializer.validated_data["species"]["genus"]["name"]
        # genus = Genus.objects.get(name=genusName)
        # speciesName = serializer.validated_data["species"]["name"]
        # species = Species.objects.get(genus=genus, name=speciesName)
        species_id = serializer.validated_data["species"]["id"]
        species = serializers.Species.objects.get(id=species_id)
        # print(species)
        genus = species.genus
        flight = serializer.save(
            owner=self.request.user,
            genus=genus,
            species=species,
            dateRecorded=date,
            location=location,
            latitude=location.y,
            longitude=location.x,
        )

        weatherThread = Thread(target=get_weather_for_flight, args=(flight,))

        weatherThread.start()

        notificationThread = Thread(
            target=self.notify_users_flight_creation, args=[flight]
        )
        notificationThread.start()

        # getWeatherForFlight(flight)
        event = "Flight created."

        serializers.Changelog.objects.create(
            user=user, date=date, flight=flight, event=event
        )

        return Response(
            serializers.FlightSerializer(instance=flight).data,
            status=status.HTTP_201_CREATED,
        )

    def generate_changelog(self, serializer):
        # print("Starting changelog")
        flight = self.get_object()
        user = self.request.user
        date = timezone.now().replace(microsecond=0)

        events = []
        # hasChanged=False

        # print(serializer.validated_data)

        species_id = serializer.validated_data["species"]["id"]
        new_species = serializers.Species.objects.get(pk=species_id)
        new_genus = new_species.genus
        # new_genus = Genus.objects.get(name=genus_name)
        # new_species = Species.objects.get(genus=new_genus, name=serializer.validated_data["species"]["name"])
        new_confidence = serializer.validated_data["confidence"]

        new_location = serializer.validated_data["location"]

        new_latitude = new_location["y"]
        new_longitude = new_location["x"]
        new_radius = serializer.validated_data["radius"]
        new_date_of_flight = serializer.validated_data["dateOfFlight"]
        new_size = serializer.validated_data["size"]
        new_image = None
        removed_image = False

        if serializer.validated_data["hasImage"]:
            try:
                new_image = serializer.validated_data["image"]
            except:
                new_image = None
        else:
            if flight.image:
                flight.image.delete()
                removed_image = True
            new_image = None

        if new_genus != flight.genus:
            events.append(f"Genus changed from {flight.genus} to {new_genus}.")
        if new_species != flight.species:
            events.append(f"Species changed from {flight.species} to {new_species}.")
        if new_confidence != flight.confidence:
            confidence_levels = ["low", "high"]

            new_level = confidence_levels[new_confidence]
            old_level = confidence_levels[flight.confidence]
            events.append(f"Confidence changed from {old_level} to {new_level}.")
        if new_latitude != flight.latitude or new_longitude != flight.longitude:
            events.append(
                f"Location changed from ({round(flight.latitude,3)}, {round(flight.longitude, 3)}) to ({round(new_latitude, 3)}, {round(new_longitude, 3)})."
            )
        if new_radius != flight.radius:
            events.append(
                f"Radius changed from {round(flight.radius, 1)} km to {round(new_radius, 1)} km."
            )
        if new_date_of_flight != flight.dateOfFlight:
            # print("Old date: {}".format(flight.dateOfFlight))
            # print("New date: {}".format(new_date_of_flight))
            old_date_string = flight.dateOfFlight.strftime("%I:%M %p %Z on %d %b %Y")
            new_date_string = new_date_of_flight.strftime("%I:%M %p %Z on %d %b %Y")
            events.append(
                f"Date of flight changed from {old_date_string} to {new_date_string}."
            )
        if new_size != flight.size:
            events.append(f"Size of flight changed from {flight.size} to {new_size}.")
        if new_image:
            events.append("Image changed.")
        if removed_image:
            events.append("Image Removed.")

        # event = event.rstrip()
        event = "\n".join(events)

        serializers.Changelog.objects.create(
            user=user, flight=flight, event=event, date=date
        )
        # print("Done changelog")

    def generate_notification_body_update(self):
        flight = self.get_object()
        return f"A {flight.genus.name} {flight.species.name} flight (id {flight.flightID}) has been updated by {flight.owner.username}"

    def notify_users_update(self):
        body = self.generate_notification_body_update()
        flight = self.get_object()
        species = flight.species
        flight_id = flight.flightID
        owner = flight.owner
        # users = species.flightuser_set.all()
        genus = flight.genus
        # users = users.union(genus.flightuser_set.all())
        # devices = Device.objects.filter(user__flightuser__in=users).exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).exclude(user=owner).values_list('deviceToken', flat=True)

        # species = flight.species
        species_users = species.flightuser_set.all()
        # genus = flight.genus
        genus_users = genus.flightuser_set.all()
        species_devices = (
            models.Device.objects.filter(user__flightuser__in=species_users)
            .exclude(deviceToken="")
            .exclude(authToken=None)
            .exclude(authToken__expiry__lte=timezone.now())
            .exclude(user=flight.owner)
            .values_list("deviceToken", flat=True)
        )
        genus_devices = (
            models.Device.objects.filter(user__flightuser__in=genus_users)
            .exclude(deviceToken="")
            .exclude(authToken=None)
            .exclude(authToken__expiry__lte=timezone.now())
            .exclude(user=flight.owner)
            .values_list("deviceToken", flat=True)
        )

        devices = genus_devices.union(species_devices)

        title = "Flight Edited"

        # sendAllNotifications("Flight Edited", body, devices, flightID=flight_id)
        notifications.send_notifications(devices=devices, title=title, body=body)

    def update(self, request, pk=None, format=None):
        # print("Making serializer")
        serializer = serializers.FlightSerializer(data=self.request.data)
        # print("Made serializer")

        if not serializer.is_valid():
            return Response(status=status.HTTP_400_BAD_REQUEST)

        self.generate_changelog(serializer)

        # print("Saving serializer")
        flight = self.get_object()
        instance = serializer.update(flight, serializer.validated_data)
        # instance = serializer.save()
        # print("Saved serializer")

        notificationThread = Thread(target=self.notify_users_update, args=[])
        notificationThread.start()

        return Response(serializer.data, status=status.HTTP_200_OK)

    def notify_user_verify(self, request, flightID, validated):
        f = serializers.Flight.objects.get(pk=flightID)
        taxonomy = str(f.species)
        u = f.owner
        devices = (
            u.devices.exclude(deviceToken="")
            .exclude(authToken=None)
            .exclude(authToken__expiry__lte=timezone.now())
            .values_list("deviceToken", flat=True)
        )

        if validated:
            title = "Flight Verified"
            body = f"Your {taxonomy} flight (id {flightID}) has been verified by {self.request.user.username}."
        else:
            title = "Flight Unverified"
            body = f"Your {taxonomy} flight (id {flightID}) has been unverified by {self.request.user.username}."

        # sendAllNotifications(title, body, devices, flightID=flightID)
        notifications.send_notifications(devices=devices, title=title, body=body)

    @action(detail=True, methods=["GET"])
    def verify(self, request, pk=None, format=None):
        flight = serializers.Flight.objects.get(pk=pk)

        if flight.validatedBy:
            username = flight.validatedBy.user.username
        else:
            username = None

        data = {
            "flightID": pk,
            "validated": flight.isValidated(),
            "validatedBy": username,
            "validatedAt": flight.validatedAt,
        }
        serializer = serializers.FlightValidationSerializer(data=data)

        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @verify.mapping.post
    def verify_flight(self, request, pk=None, format=None):
        serializer = serializers.FlightValidationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # flightID = int(serializer.validated_data["flightID"])

        # if flightID != pk:
        #     return Response({"Errors": "Incorrect flight ID"}, status=status.HTTP_400_BAD_REQUEST)

        flight = serializers.Flight.objects.get(pk=pk)

        validate = serializer.validated_data["validate"]

        if validate:
            flight.validatedBy = request.user.flightuser
            timeOfValidation = timezone.now().replace(microsecond=0)
            flight.validatedAt = timeOfValidation

            flight.save()

            serializers.Changelog.objects.create(
                user=request.user,
                flight=flight,
                event=f"Flight verified by {request.user.username}.",
                date=timeOfValidation,
            )

        else:
            flight.validatedBy = None
            flight.validatedAt = None

            flight.save()

            serializers.Changelog.objects.create(
                user=request.user,
                flight=flight,
                event=f"Flight unverified by {request.user.username}.",
                date=timezone.now().replace(microsecond=0),
            )

        notificationThread = Thread(
            target=self.notify_user_verify, args=[request, pk, validate]
        )
        notificationThread.start()

        if flight.isValidated():
            username = flight.validatedBy.user.username
        else:
            username = None

        data = {
            "flightID": pk,
            "validated": flight.isValidated(),
            "validatedBy": username,
            "validatedAt": flight.validatedAt,
        }

        responseSerializer = serializers.FlightValidationSerializer(data=data)

        if responseSerializer.is_valid():
            return Response(responseSerializer.data, status=status.HTTP_200_OK)
        else:
            return Response(
                responseSerializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True)
    def history(self, request, pk=None, format=None):
        flight = get_object_or_404(serializers.Flight.objects.all(), flightID=pk)
        changelog_entries = (
            serializers.Changelog.objects.all().filter(flight=flight).order_by("-date")
        )
        serializer = serializers.ChangelogSerializer(changelog_entries, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True)
    def weather(self, request, pk=None, format=None):
        weather = get_object_or_404(serializers.Weather.objects.all(), flight_id=pk)
        serializer = serializers.WeatherSerializer(weather)

        return Response(serializer.data, status=status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):

    serializer_class = serializers.CommentSerializer
    # permission_classes = [IsOwnerOrReadOnly]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.permissions.IsAuthenticated()]
        if self.action not in ["list", "retrieve"]:
            return [permissions.IsAuthorOrReadOnly()]
        return []

    def get_queryset(self):
        return serializers.Comment.objects.filter(
            responseTo__flightID=self.kwargs["flight_pk"]
        )

    def notify_user_comment(self, author, flight):
        flightID = flight.flightID
        taxonomy = str(flight.species)
        u = flight.owner
        devices = (
            u.devices.exclude(deviceToken="")
            .exclude(authToken=None)
            .exclude(authToken__expiry__lte=timezone.now())
            .values_list("deviceToken", flat=True)
        )

        title = "New Comment"
        body = f"{author.username} has left a new comment on your {taxonomy} flight (id {flightID})."

        # sendAllNotifications(title, body, devices, flightID=flightID)
        notifications.send_notifications(devices=devices, title=title, body=body)

    def create(self, request, *args, **kwargs):
        # print(serializer.validated_data)
        # author = User.objects.get(username=serializer.validated_data["author"])
        serializer = serializers.CommentSerializer(data=self.request.data)
        if not serializer.is_valid():
            return Response(status=status.HTTP_400_BAD_REQUEST)

        text = serializer.validated_data["text"]
        # flightID = serializer.validated_data["responseTo"]["flightID"]
        flight_id = self.kwargs["flight_pk"]
        responseTo = serializers.Flight.objects.get(pk=flight_id)
        author = self.request.user
        time = timezone.now().replace(
            microsecond=0
        )  # serializer.validated_data["time"]

        comment = serializers.Comment.objects.create(
            author=author, text=text, responseTo=responseTo, time=time
        )

        if author != responseTo.owner:
            notificationThread = Thread(
                target=self.notify_user_comment, args=[author, responseTo]
            )
            notificationThread.start()

        return Response(
            serializers.CommentSerializer(instance=comment).data,
            status=status.HTTP_201_CREATED,
        )


class FlightImageViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
):

    parser_classes = [ImageUploadParser]
    serializer_class = serializers.FlightImageSerializer
    # permission_classes = [IsOwnerOrReadOnly]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsFlightOwnerOrReadOnly(self.kwargs["flight_pk"])]

        return [permissions.IsImageOwnerOrReadOnly()]

    def get_queryset(self):
        return serializers.FlightImage.objects.filter(
            flight__flightID=self.kwargs["flight_pk"]
        )

    # def notify_user_comment(self, author, flight):
    #     flightID = flight.flightID
    #     taxonomy = str(flight.species)
    #     u = flight.owner
    #     devices = u.devices.exclude(deviceToken=None).exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now())

    #     title = "New Comment"
    #     body = f"{author.username} has left a new comment on your {taxonomy} flight (id {flightID})."

    #     sendAllNotifications(title, body, devices, flightID=flightID)

    def create(self, request, *args, **kwargs):
        image = self.request.data["file"]
        created_by = self.request.user
        date_created = timezone.now().replace(microsecond=0)
        flight = serializers.Flight.objects.get(pk=self.kwargs["flight_pk"])

        try:
            pil_image = Image.open(image)
            pil_image.verify()
        except:
            raise ParseError("Incorrect file type provided.")

        flight_image = serializers.FlightImage.objects.create(
            image=image, created_by=created_by, date_created=date_created, flight=flight
        )
        flight_image.save()

        serializer = serializers.FlightImageSerializer(instance=flight_image)

        changelog_text = "-Added Image"
        changelog_entry = serializers.Changelog.objects.create(
            flight=flight, event=changelog_text, date=date_created, user=created_by
        )
        # changelog_entry.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        image_id = self.get_object().id
        flight = self.get_object().flight
        destroy_response = super().destroy(request, *args, **kwargs)

        changelog_text = "-Removed image {}".format(image_id)

        changelog_entry = serializers.Changelog.objects.create(
            flight=flight,
            event=changelog_text,
            date=timezone.now().replace(microsecond=0),
            user=self.request.user,
        )
        # changelog_entry.save()

        return destroy_response

    # def update(self, request, *args, **kwargs):
    #     image = request.data.get("file")

    #     if image is None:
    #         raise ParseError("No image")

    #     flight_image = self.get_object()

    #     try:
    #         pil_image = Image.open(image)
    #         pil_image.verify()
    #     except:
    #         raise ParseError("Incorrect file type provided.")

    #     flight_image.image = image
    #     flight_image.save()

    #     serializer = FlightImageSerializer(flight_image)

    #     return Response(serializer.data, status=status.HTTP_200_OK)

    # def delete(self, request, *args, **kwargs):
    #     flight_image = self.get_object()

    #     flight_image.delete()


class TaxonomyVersionView(APIView):

    # permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        taxonomy = serializers.Taxonomy.objects.last()
        serializer = serializers.TaxonomyVersionSerializer(taxonomy)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FullTaxonomyView(APIView):
    """
    API view that returns all genera and species.
    """

    def get(self, request, *args, **kwargs):
        taxonomy = serializers.Taxonomy.objects.last()
        genera = taxonomy.genera
        serializer = serializers.FullTaxonomySerializer(genera, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def welcome(request, update_development=False):
    return render(
        request, "nuptiallog/Welcome.html", {"update_development": update_development}
    )


def about(request, update_development=False):
    return render(
        request, "nuptiallog/About.html", {"update_development": update_development}
    )


def download(request, update_development=False):
    formats = ["xlsx", "csv", "json", "xls"]
    return render(
        request,
        "nuptiallog/DownloadData.html",
        {"formats": formats, "update_development": update_development},
    )


def communityStandards(request, update_development=False):
    return render(
        request,
        "nuptiallog/CommunityStandards.html",
        {"update_development": update_development},
    )


def terms(request, mobile=False, update_development=False):
    return render(
        request,
        "nuptiallog/TermsAndConditions.html",
        {"mobile": mobile, "update_development": update_development},
    )


def privacy(request, update_development=False):
    return render(
        request,
        "nuptiallog/PrivacyPolicy.html",
        {"update_development": update_development},
    )


def scientificAdvisoryBoard(request, update_development=False):
    scientists = models.ScientificAdvisor.objects.all()

    return render(
        request,
        "nuptiallog/ScientificAdvisoryBoard.html",
        {"scientists": scientists, "update_development": update_development},
    )


def helpView(request, update_development=False):
    # questions = getFaqs()
    return render(
        request, "nuptiallog/Help.html", {"update_development": update_development}
    )


def applicense(request):
    # path = sys.path("AntNupTrackerLicense.txt")
    # license = open(path)
    currentDir = os.path.dirname(__file__)
    licensePath = os.path.join(currentDir, "AntNupTrackerLicense.txt")
    license = open(licensePath)
    licenseText = license.read()
    license.close()
    return HttpResponse(licenseText, content_type="text/plain")
    # return render(request, 'nuptiallog/AntNupTrackerLicense.txt', content_type="text/plain")


def serverlicense(request):
    currentDir = os.path.dirname(__file__)
    licensePath = os.path.join(currentDir, "AntNupTrackerServerLicense.txt")
    license = open(licensePath)
    licenseText = license.read()
    license.close()
    return HttpResponse(licenseText, content_type="text/plain")


def taxonomy(request):
    currentDir = os.path.dirname(__file__)
    licensePath = os.path.join(currentDir, "taxonomyRaw")
    license = open(licensePath)
    licenseText = license.read()
    license.close()
    return HttpResponse(licenseText, content_type="text/plain")


# def browse(request, start, offset, update_development=False):
#     allFlights = Flight.objects.order_by('-flightID')

#     end = start + offset

#     show_next = end <= len(allFlights) + 1
#     show_prev = start - offset >= 0

#     flights = allFlights[start: end]

#     return render(request, 'nuptiallog/Browse.html', {"flights": flights, "next_start":end, "offset":offset, "prev_start":start-offset, "show_next": show_next, "show_prev": show_prev, "update_development": update_development})
