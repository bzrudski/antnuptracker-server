#
#  views.py
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

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import QuerySet
from rest_framework import mixins
from rest_framework import generics
from rest_framework import permissions
from rest_framework import status
from .models import Flight, Comment, Changelog, Weather, Role, Device, Genus, Species
from .serializers import FlightSerializer, CommentSerializer, FlightUserSerializer, FlightSerializerBarebones, ChangelogSerializer, WeatherSerializer, SpeciesSerializer, SpeciesListSerializer, GenusSerializer, GenusListSerializer, FlightSerializerFull, FlightSerializerExport
from .permissions import IsOwnerOrReadOnly, IsOwner, IsProfessional
from .weather import getWeatherForFlight
from .notifications import sendAllNotifications
from .paginators import BiggerPagesPaginator
from .faq import getFaqs

from knox.views import LoginView as KnoxLoginView
from rest_framework.authentication import BasicAuthentication

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from .taxonomy import GENERA, SPECIES

from django.contrib.auth.models import User, AnonymousUser
from django.contrib.auth.password_validation import validate_password, UserAttributeSimilarityValidator
from .serializers import UserSerializer
from .models import FlightUser, Device
from django.contrib.auth.hashers import make_password

from .forms import UserCreationForm, PasswordResetForm, PasswordChangeForm
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from .tokens import accountActivationToken, passwordResetToken
from django.core.mail import EmailMessage
#from django.contrib.auth import login, authenticate

from django.views import generic
from django.utils import timezone

from nuptialtracker.settings import MEDIA_ROOT

from threading import Thread
import io
import json
import os
import sys

# Create your views here.
class GenusListView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({"genera":GENERA}, status=status.HTTP_200_OK)

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
            return Response({"species":speciesList}, status=status.HTTP_200_OK)
        except:
            return Response("Invalid genus", status=status.HTTP_404_NOT_FOUND)

class FlightList(mixins.ListModelMixin, mixins.CreateModelMixin, generics.GenericAPIView):
    # queryset = Flight.objects.all().order_by('-dateRecorded')
    serializer_class = FlightSerializerBarebones
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    # ordering = ['-dateRecorded']

    def get_queryset(self):
        queryset = Flight.objects.all().order_by('-dateRecorded')

        genus = self.request.query_params.get('genus', None)
        if genus != None:
            queryset = queryset.filter(genus__name=genus)

            species = self.request.query_params.get('species', None)
            if species != None:
                queryset = queryset.filter(species__name=species)

        return queryset

    def generate_notification_body(self, flight):
        return f"A new {flight.genus.name} {flight.species.name} flight (id {flight.flightID}) has been recorded by {flight.owner.username}."

    def notify_users(self, flight):
        body = self.generate_notification_body(flight)
        species = flight.species
        users = species.flightuser_set.all()
        devices = Device.objects.filter(user__flightuser__in=users).exclude(deviceToken=None).exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).exclude(user=flight.owner)

        sendAllNotifications("Flight Created", body, devices, flightID=flight.flightID)

    def perform_create(self, serializer):
        user = self.request.user
        date = timezone.now().replace(microsecond=0)
        # print(serializer.validated_data)
        #genusName = serializer.validated_data["genus"]["name"]
        # genus = Genus.objects.get(name=genusName)
        genusName = serializer.validated_data["species"]["genus"]["name"]
        genus = Genus.objects.get(name=genusName)
        speciesName = serializer.validated_data["species"]["name"]
        species = Species.objects.get(genus=genus, name=speciesName)
        flight = serializer.save(owner=self.request.user, genus=genus, species=species)

        weatherThread = Thread(target=getWeatherForFlight, args=(flight, ))

        weatherThread.start()

        notificationThread = Thread(target=self.notify_users, args=[flight])
        notificationThread.start()

        #getWeatherForFlight(flight)
        event = "Flight created."

        Changelog.objects.create(user=user, date=date, flight=flight, event=event)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

class FlightDetail(mixins.RetrieveModelMixin,mixins.UpdateModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
    queryset = Flight.objects.all()
    serializer_class = FlightSerializer
    permission_classes = (IsOwnerOrReadOnly,)

    def generate_changelog(self, serializer):
        # print("Starting changelog")
        flight = self.get_object()
        user = self.request.user
        date = timezone.now().replace(microsecond=0)

        event = ""
        #hasChanged=False

        genusName = serializer.validated_data["species"]["genus"]["name"]
        newGenus = Genus.objects.get(name=genusName)
        newSpecies = Species.objects.get(genus=newGenus, name=serializer.validated_data["species"]["name"])
        newConfidence = serializer.validated_data["confidence"]
        newLat = serializer.validated_data["latitude"]
        newLong = serializer.validated_data["longitude"]
        newRadius = serializer.validated_data["radius"]
        newDateOfFlight = serializer.validated_data["dateOfFlight"]
        newSize = serializer.validated_data["size"]
        newImage = None

        # try:
        #     newImage = serializer.validated_data["image"]
        # except:
        #     newImage = None
    
        if (serializer.validated_data["hasImage"]):
            try:
                newImage = serializer.validated_data["image"]
            except:
                newImage = None
        else:
            if flight.image:
                flight.image.delete()
            newImage = None

        if (newGenus != flight.genus):
            event += f"- Genus changed from {flight.genus} to {newGenus}\n"
        if (newSpecies != flight.species):
            event += f"- Species changed from {flight.species} to {newSpecies}\n"
        if (newConfidence != flight.confidence):
            confidenceLevels = ["low", "high"]

            newLevel = confidenceLevels[newConfidence]
            oldLevel = confidenceLevels[flight.confidence]
            event += f"- Confidence changed from {oldLevel} to {newLevel}\n"
        if (newLat != flight.latitude or newLong != flight.longitude):
            event += f"- Location changed from ({round(flight.latitude,3)}, {round(flight.longitude, 3)}) to ({round(newLat, 3)}, {round(newLong, 3)})\n"
        if (newRadius != flight.radius):
            event += f"- Radius changed from {round(flight.radius, 1)} km to {round(newRadius, 1)} km\n"
        if (newDateOfFlight != flight.dateOfFlight):
            oldDateString = flight.dateOfFlight.strftime("%I:%M %p %Z on %d %b %Y")
            newDateString = newDateOfFlight.strftime("%I:%M %p %Z on %d %b %Y")
            event += f"- Date of flight changed from {oldDateString} to {newDateString}\n"
        if (newSize != flight.size):
            event += f"- Size of flight changed from {flight.size} to {newSize}\n"
        if (newImage):
            event += "- Image changed.\n"

        event = event.rstrip()

        Changelog.objects.create(user=user, flight=flight, event=event, date=date)
        # print("Done changelog")

    def generate_notification_body(self):
        flight = self.get_object()
        return f"A {flight.genus.name} {flight.species.name} flight (id {flight.flightID}) has been updated by {flight.owner.username}"

    def notify_users(self):
        body = self.generate_notification_body()
        flight = self.get_object()
        species = flight.species
        flightID = flight.flightID
        owner = flight.owner
        users = species.flightuser_set.all()
        devices = Device.objects.filter(user__flightuser__in=users).exclude(deviceToken=None).exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).exclude(user=owner)

        sendAllNotifications("Flight Edited", body, devices, flightID=flightID)

    def perform_update(self, serializer):
        self.generate_changelog(serializer)

        serializer.save()

        notificationThread = Thread(target=self.notify_users, args=[])
        notificationThread.start()

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

class ValidateFlight(APIView):
    permission_classes = [IsProfessional]

    def notify_user(self, request, flightID):
        f = Flight.objects.get(pk=flightID)
        taxonomy = str(f.species)
        u = f.owner
        devices = u.devices.exclude(deviceToken=None).exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now())

        title = "Flight Validated"
        body = f"Your {taxonomy} flight (id {flightID}) has been validated by {self.request.user.username}."

        sendAllNotifications(title, body, devices, flightID=flightID)

    def get(self, request, pk):
        try:
            f = Flight.objects.get(pk=pk)
            if f.isValidated() :
                response = {"validated": True}
            else :
                response = {"validated": False}
            return Response(response, status=status.HTTP_200_OK)
        except Flight.DoesNotExist:
            return Response("No flight with that id.", status=status.HTTP_404_NOT_FOUND)

    def post(self, request, pk):
        try:
            f = Flight.objects.get(pk=pk)
            if f.isValidated():
                return HttpResponse("Flight already validated.", status=status.HTTP_200_OK)
            f.validatedBy = request.user.flightuser
            f.save()
            timeOfValidation = timezone.now().replace(microsecond=0)
            f.validatedAt = timeOfValidation
            f.save()

            Changelog.objects.create(user=request.user, flight=f, event=f"Flight validated by {request.user.username}.", date=timeOfValidation)

            notificationThread = Thread(target=self.notify_user, args=[request, pk])
            notificationThread.start()

            return Response("Flight validated.", status=status.HTTP_200_OK)
        except Flight.DoesNotExist:
            return Response("No flight with that id.", status=status.HTTP_404_NOT_FOUND)

class MyFlightsList(mixins.ListModelMixin, generics.GenericAPIView):
    serializer_class = FlightSerializerBarebones
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Flight.objects.all().filter(owner=self.request.user)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

class MySpeciesList(mixins.ListModelMixin, generics.GenericAPIView):
    serializer_class = SpeciesSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = BiggerPagesPaginator

    def get_queryset(self):
        return Species.objects.all().filter(flightuser=self.request.user.flightuser)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = SpeciesListSerializer(data=request.data)

        # print("Preparing to update species list")

        if (serializer.is_valid()):
            species = serializer.validated_data["species"]

            for species in species:
                # print("Adding species: "+str(species))
                user.flightuser.species.add(species)
                # print("Species added: "+str(species))

            return Response("Species list modified", status=status.HTTP_200_OK)
        # print(serializer.errors)
        return Response("Bad request", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        user = request.user
        serializer = SpeciesListSerializer(data=request.data)

        if (serializer.is_valid()):
            speciesList = serializer.validated_data["species"]

            for species in speciesList:
                # print("Removing species: "+str(species))
                user.flightuser.species.remove(species)

            return Response("Species list modified", status=status.HTTP_200_OK)
        # print(serializer.errors)
        return Response("Bad request", status=status.HTTP_400_BAD_REQUEST)

class MyGenusList(mixins.ListModelMixin, generics.GenericAPIView):
    serializer_class = GenusSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = BiggerPagesPaginator

    def get_queryset(self):
        return Genus.objects.all().filter(flightuser=self.request.user.flightuser)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = GenusListSerializer(data=request.data)

        # print("Preparing to update genus list")

        if (serializer.is_valid()):
            genera = serializer.validated_data["genus"]

            for genus in genera:
                # print("Adding genus: "+str(genus))
                user.flightuser.genera.add(genus)
                # print("Genus added: "+str(genus))

            return Response("Genus list modified", status=status.HTTP_200_OK)
        # print(serializer.errors)
        return Response("Bad request", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        user = request.user
        serializer = GenusListSerializer(data=request.data)

        if (serializer.is_valid()):
            genusList = serializer.validated_data["genera"]

            for genus in genusList:
                # print("Removing genus: "+str(genus))
                user.flightuser.genus.remove(genus)

            return Response("Genus list modified", status=status.HTTP_200_OK)
        # print(serializer.errors)
        return Response("Bad request", status=status.HTTP_400_BAD_REQUEST)

class UpdateMySpeciesList(APIView):
    #serializer_class = SpeciesModificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    queryset = Species.objects.all()

    def update(self, request):
        user = self.request.user
        toAdd = request.data["toAdd"]
        # toRemove = request.data["toRemove"]

        return Response(toAdd[0])
        # print(toRemove)

    def post(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class ImageView(APIView):
    def get(self, request, filename):
        # print(filename)
        path = str(MEDIA_ROOT) + "/flight_pics/" + filename

        if os.path.exists(path):
            imageFile = open(path, 'rb')
            image = imageFile.read()
            imageFile.close()
            return HttpResponse(image, content_type="image/png")
        
        else:
            return Response("No such image", status=status.HTTP_404_NOT_FOUND)

class CommentList(mixins.ListModelMixin, mixins.CreateModelMixin, generics.GenericAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def notify_user(self, author, flight):
        flightID = flight.flightID
        taxonomy = str(flight.species)
        u = flight.owner
        devices = u.devices.exclude(deviceToken=None).exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now())

        title = "New Comment"
        body = f"{author.username} has left a new comment on your {taxonomy} flight (id {flightID})."

        sendAllNotifications(title, body, devices, flightID=flightID)

    def perform_create(self, serializer):
        # print(serializer.validated_data)
        #author = User.objects.get(username=serializer.validated_data["author"])
        text = serializer.validated_data["text"]
        flightID = serializer.validated_data["responseTo"]["flightID"]
        responseTo = Flight.objects.get(pk=flightID)
        author = self.request.user
        time = timezone.now().replace(microsecond=0) #serializer.validated_data["time"]

        comment = Comment.objects.create(author=author, text=text, responseTo=responseTo, time=time)

        if (author == responseTo.owner):
            return

        notificationThread = Thread(target=self.notify_user, args=[author, responseTo])
        notificationThread.start()

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

class CommentDetail(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, generics.GenericAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

class ChangelogForFlight(mixins.ListModelMixin, generics.GenericAPIView):
    #queryset = Changelog.objects.all()
    serializer_class = ChangelogSerializer
    pagination_class = None
    lookup_field = "flightID"
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return Changelog.objects.all().filter(flight_id=self.kwargs["pk"]).order_by('-date')

    def get(self,request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

class WeatherForFlight(mixins.RetrieveModelMixin, generics.GenericAPIView):
    serializer_class = WeatherSerializer
    lookup_field = "flight_id"
    lookup_url_kwarg = "pk"

    def get_object(self):
        queryset = self.get_queryset()
        filter = {"flight_id": self.kwargs["pk"]}

        weather = get_object_or_404(queryset, **filter)

        self.check_object_permissions(self.request, weather)
        return weather

    def get_queryset(self):
        try:
            return Weather.objects.all()
        except:
            return None

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

class UserListView(mixins.ListModelMixin, generics.GenericAPIView):
    queryset = FlightUser.objects.all()
    serializer_class = FlightUserSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

class LoginView(KnoxLoginView):
    authentication_classes = [BasicAuthentication]
    alphanumerics = "abcdefghijklmnopqrstuvwxyz1234567890"

    def get_user_serializer_class(self):
        return FlightUserSerializer

    def get_post_response_data(self, request, token, instance):
        UserSerializer = self.get_user_serializer_class()

        # print(request.data)

        deviceID = self.getDeviceID(request, instance)

        if (not deviceID):
            deviceID = 0

        data = {
            'expiry'    : self.format_expiry_datetime(instance.expiry),
            'token'     : token,
            'deviceID'  : deviceID,
        }

        # if UserSerializer is not None:
        #     data.update(UserSerializer(
        #         request.user,
        #         context=self.get_context()
        #     ).data)

        data.update(FlightUserSerializer(request.user.flightuser, context=self.get_context()).data)

        return data

    def getDeviceID(self, request, authToken)->int:
        device = None
        deviceID = 0

        deviceID = self.request.META.get("HTTP_DEVICEID")
        platform = self.request.data.get("platform")
        model = self.request.data.get("model")
        deviceToken = self.request.data.get("deviceToken")
        user = self.request.user
        lastLoggedIn = timezone.now().replace(microsecond=0)

        try:
            if not deviceID:
                raise Exception("No device id provided.")

            device = Device.objects.get(deviceID)
            # print("Using stored")

            if (device.user != user):
                return None

            if (device.platform != platform):
                return None

            if (device.model != model):
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
                
                if (deviceToken == None):
                    raise Exception('No device token')

                for c in deviceToken:
                    if not (c in LoginView.alphanumerics):
                        deviceToken = None
                        raise Exception("Illegal token")

                device = Device.objects.get(deviceToken=deviceToken)
                deviceID = device.deviceID
                # print("Found device by token")
                # print(f"Device ID is now {deviceID}")

                if (device.model != model):
                    raise Exception('Wrong model')

                if (device.platform != platform):
                    raise Exception('Wrong platform')

                if (device.user != user):
                    device.user = user
                    device.save()

                device.lastLoggedIn = timezone.now().replace(microsecond=0)
                device.authToken = authToken
                device.save()

                return device.deviceID

            except:
                deviceID = Device.generate_new_id()
                # print("Create new.")
                # print(f"Device ID is now {deviceID}")
                device = Device.objects.create(
                    deviceID=deviceID,
                    model=model,
                    platform=platform,
                    authToken=authToken,
                    deviceToken=deviceToken,
                    lastLoggedIn=lastLoggedIn,
                    user=self.request.user
                )
                device.save()
                return device.deviceID

        # finally:
        #     print(deviceID, end='\n')
        #     #if (not deviceID == None):
        #     # device.authToken = authToken
        #     # device.save()
        #     return deviceID

class VerifyTokenView(APIView):
    def post(self, request, format=None):
        auth = request.auth
        if (request.auth != None):
            user = request.user.flightuser
            # role = user.role.role
            deviceID = self.request.META['HTTP_DEVICEID']
            try:
                device = Device.objects.get(deviceID=deviceID)

                device.lastLoggedIn = timezone.now()
                device.active = True
                device.save()
            except:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

            return Response({"message": "Login verified"}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_401_UNAUTHORIZED)

class CreateUserForm(generic.FormView):
    # In part based on code from 
    # # https://medium.com/@frfahim/django-registration-with-confirmation-email-bb5da011e4ef 
    # by Farhadur Reja Fahim
    formTemplate = 'nuptiallog/AccountCreateForm.html'
    emailSuccessful = 'nuptiallog/EmailSent.html'
    emailFailed = 'nuptiallog/EmailFailed.html'

    def post(self, request, *args, **kwargs):
        form = UserCreationForm(request.POST)
        if (form.is_valid()):
            emailAddr = form.cleaned_data["email"]

            if (len(User.objects.all().filter(email=emailAddr)) != 0):
                form.errors.update({"email":["A user with that email address already exists"]})
                return render(request, self.formTemplate, {'form':form})

            professional = form.cleaned_data["professional"]
            institution = form.cleaned_data["institution"]

            if (professional and not institution):
                form.errors.update({"institution": ["You must enter your institution"]})
                return render(request, self.formTemplate, {'form':form})

            user = form.save(commit=False)
            user.is_active = False
            # user.username = user.username.lower()
            user.save()
            user.flightuser.professional = professional
            user.flightuser.institution = institution
            user.flightuser.description = form.cleaned_data["description"]
            
            #role = Role.objects.get(pk=form.cleaned_data["role"])
            user.save()
            user.flightuser.save()
            # print("User saved")
            currentSite = get_current_site(request)
            subject = "Activate NuptialTracker Account"
            message = render_to_string('nuptiallog/ActivateEmail.html', {
                'user': user,
                'domain': currentSite.domain,
                'uid':  urlsafe_base64_encode(force_bytes(user.pk)),
                'token': accountActivationToken.make_token(user)
            })
            to_email=form.cleaned_data.get('email')
            email = EmailMessage(subject, message, to=[to_email])
            email.content_subtype = 'html'
            # print("Preparing to send e-mail.")
            try:
                email.send()

                # print("Sent e-mail")
                return render(request, 'nuptiallog/EmailSent.html', {'user':user}, status=status.HTTP_201_CREATED)
            except:
                # print("Error sending e-mail.")
                return render(request, self.emailFailed, {'user':user}, status=400)
        else:
            return render(request, self.formTemplate, {'form':form})
    def get(self, request, *args, **kwargs):
        form = UserCreationForm()
        return render(request, self.formTemplate, {'form':form})


# Password reset based on https://medium.com/@renjithsraj/how-to-reset-password-in-django-bd5e1d6ed652 by Renjith S Raj

class ResetPasswordForm(generic.FormView):
    mobile = False
    formTemplate = 'nuptiallog/PasswordResetForm.html'
    emailSuccessful = 'nuptiallog/EmailSentPassChange.html'
        
    def post(self, request, *args, **kwargs):
        form = PasswordResetForm(request.POST)
        if (form.is_valid()):
            to_email=form.cleaned_data.get('email')
            user = User.objects.get(email=to_email)

            currentSite = get_current_site(request)
            subject = "Reset NuptialTracker Password"
            message = render_to_string('nuptiallog/PasswordResetEmail.html', {
                'user': user,
                'domain': currentSite.domain,
                'uid':  urlsafe_base64_encode(force_bytes(user.pk)),
                'token': passwordResetToken.make_token(user)
            })
            email = EmailMessage(subject, message, to=[to_email])
            email.content_subtype = 'html'
            # print("Preparing to send e-mail.")
            email.send()

            # print("Sent e-mail")
            return render(request, self.emailSuccessful, {'user':user, 'mobile': self.mobile}, status=status.HTTP_201_CREATED)
        else:
            return render(request, self.formTemplate, {'form':form, 'mobile': self.mobile})
    def get(self, request, *args, **kwargs):
        form = PasswordResetForm()
        return render(request, self.formTemplate, {'form':form, 'mobile': self.mobile})

class UserActivationView(generic.View):
    def activate(self, request, uidb64, token):
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except:
            user = None

        if (user is not None and accountActivationToken.check_token(user, token)):
            user.is_active = True
            user.save()
            return render(request, 'nuptiallog/SuccessActivation.html', {'user':user})
        else:
            return render(request, 'nuptiallog/FailureActivation.html', status=status.HTTP_404_NOT_FOUND)

    def get(self, request, uidb64, token):
        return self.activate(request, uidb64, token)

class ChangePasswordForm(generic.FormView):
    def getUser(self, uidb64):
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except:
            user = None

        return user

    def get(self, request, uidb64, token):

        user = self.getUser(uidb64)

        if (user is not None and passwordResetToken.check_token(user, token)):
            form = PasswordChangeForm()
            return render(request, 'nuptiallog/PassChangeForm.html', {'form':form, 'user':user})
        return render(request, 'nuptiallog/FailurePassChange.html', status=status.HTTP_404_NOT_FOUND)

    def post(self, request, uidb64, token):
        user = self.getUser(uidb64)

        if (user is not None and passwordResetToken.check_token(user, token)):
            form = PasswordChangeForm(request.POST)
            if (form.is_valid()):
                uid = force_text(urlsafe_base64_decode(uidb64))
                user = User.objects.get(pk=uid)
                # print(user)
                user.set_password(form.cleaned_data["password1"])
                user.save()
                return render(request, 'nuptiallog/SuccessPassChange.html', {'user':user})
            else:
                return render(request, 'nuptiallog/PassChangeForm.html', {'form':form, 'user':user})
        else:
            return render(request, 'nuptiallog/FailurePassChange.html', status=status.HTTP_404_NOT_FOUND)

class UserDetailView(mixins.RetrieveModelMixin, generics.GenericAPIView):
    serializer_class = FlightUserSerializer
    lookup_field = "user__username"
    lookup_url_kwarg = "username"

    def get_queryset(self):
        return FlightUser.objects.all().filter(user__username=self.kwargs["username"])

    def get(self,request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

class FlightListNested(APIView):
    serializer_class = FlightSerializerFull
    renderer_classes = [JSONRenderer]

    def get_data(self):
        flights = Flight.objects.all()
        serializer = FlightSerializerFull(flights, many=True)
        return serializer.data

    def get(self, request, *args, **kwargs):
        return Response(self.get_data(), status=status.HTTP_200_OK)

def welcome(request):
    return render(request, 'nuptiallog/Welcome.html')

def about(request):
    return render(request, 'nuptiallog/About.html')

def download(request):
    formats = ["xlsx", "csv", "json", "xls"]
    return render(request, 'nuptiallog/DownloadData.html', {"formats":formats})

def communityStandards(request):
    return render(request, 'nuptiallog/CommunityStandards.html')

def terms(request, mobile=False):
    return render(request, 'nuptiallog/TermsAndConditions.html', {"mobile":mobile})

def privacy(request):
    return render(request, 'nuptiallog/PrivacyPolicy.html')

def helpView(request):
    questions = getFaqs()
    return render(request, 'nuptiallog/Help.html', {"questions":questions})

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

def browse(request, start, offset):
    allFlights = Flight.objects.order_by('-dateRecorded')
    
    end = start + offset

    show_next = end <= len(allFlights) + 1
    show_prev = start - offset >= 0

    flights = allFlights[start: end]

    return render(request, 'nuptiallog/Browse.html', {"flights": flights, "next_start":end, "offset":offset, "prev_start":start-offset, "show_next": show_next, "show_prev": show_prev})