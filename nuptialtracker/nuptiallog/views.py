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

from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import QuerySet, F, Q, Count
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from rest_framework import mixins
from rest_framework import generics
from rest_framework import permissions
from rest_framework import status
from rest_framework import viewsets
from rest_framework import filters
from rest_framework import views
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ParseError
from django_filters import rest_framework as extra_filters
from PIL import Image
# from django_filters.rest_framework import DjangoFilterBackend
import rest_framework
from .models import Flight, Comment, Changelog, FlightImage, Weather, Role, Device, Genus, Species, ScientificAdvisor
from .serializers import *
# from .permissions import IsOwnerOrReadOnly, IsOwner, IsProfessional, IsProfessionalOrReadOnly, IsAuthor, IsAuthorOrReadOnly
from .permissions import *
from .weather import get_weather_for_flight
from .notifications import send_notifications
from .paginators import BiggerPagesPaginator
from .faq import getFaqs
from .parsers import ImageUploadParser
from .exceptions import BadLocationUrlException

from knox.views import LoginView as KnoxLoginView
from rest_framework.authentication import BasicAuthentication

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import FileUploadParser, JSONParser
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
        serializer = NewGenusSerializer(Genus.objects.all(), many=True)
        # return Response({"genera":GENERA}, status=status.HTTP_200_OK)
        return Response(serializer.data, status=status.HTTP_200_OK)

class GenusViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Genus.objects.all()
    serializer_class = NewGenusSerializer

    def list(self, request, *args, **kwargs):
        serializer = GenusNameIdSerializer(self.queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

class SpeciesViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):

    def get_queryset(self):
        return Species.objects.filter(genus__id=self.kwargs["genus_pk"])

    serializer_class = NewSpeciesSerializer

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
        devices = Device.objects.filter(user__flightuser__in=users).exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).exclude(user=flight.owner).values_list('deviceToken', flat=True)

        title = "Flight Created"

        # sendAllNotifications("Flight Created", body, devices, flightID=flight.flightID)
        send_notifications(devices=devices, title=title, body=body)

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
        flight = serializer.save(owner=self.request.user, genus=genus, species=species, dateRecorded=date)

        weatherThread = Thread(target=get_weather_for_flight, args=(flight, ))

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

class FlightDetail(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
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

        genus_name = serializer.validated_data["species"]["genus"]["name"]
        new_genus = Genus.objects.get(name=genus_name)
        new_species = Species.objects.get(genus=new_genus, name=serializer.validated_data["species"]["name"])
        new_confidence = serializer.validated_data["confidence"]
        new_latitude = serializer.validated_data["latitude"]
        new_longitude = serializer.validated_data["longitude"]
        new_radius = serializer.validated_data["radius"]
        new_date_of_flight = serializer.validated_data["dateOfFlight"]
        new_size = serializer.validated_data["size"]
        new_image = None

        removed_image = False

        # try:
        #     newImage = serializer.validated_data["image"]
        # except:
        #     newImage = None
    
        if (serializer.validated_data["hasImage"]):
            try:
                new_image = serializer.validated_data["image"]
            except:
                new_image = None
        else:
            if flight.image:
                flight.image.delete()
                removed_image = True
            new_image = None

        if (new_genus != flight.genus):
            event += f"- Genus changed from {flight.genus} to {new_genus}\n"
        if (new_species != flight.species):
            event += f"- Species changed from {flight.species} to {new_species}\n"
        if (new_confidence != flight.confidence):
            confidenceLevels = ["low", "high"]

            newLevel = confidenceLevels[new_confidence]
            oldLevel = confidenceLevels[flight.confidence]
            event += f"- Confidence changed from {oldLevel} to {newLevel}\n"
        if (new_latitude != flight.latitude or new_longitude != flight.longitude):
            event += f"- Location changed from ({round(flight.latitude,3)}, {round(flight.longitude, 3)}) to ({round(new_latitude, 3)}, {round(new_longitude, 3)})\n"
        if (new_radius != flight.radius):
            event += f"- Radius changed from {round(flight.radius, 1)} km to {round(new_radius, 1)} km\n"
        if (new_date_of_flight != flight.dateOfFlight):
            oldDateString = flight.dateOfFlight.strftime("%I:%M %p %Z on %d %b %Y")
            newDateString = new_date_of_flight.strftime("%I:%M %p %Z on %d %b %Y")
            event += f"- Date of flight changed from {oldDateString} to {newDateString}\n"
        if (new_size != flight.size):
            event += f"- Size of flight changed from {flight.size} to {new_size}\n"
        if new_image:
            event += "- Image changed.\n"
        if removed_image:
            event += "- Image Removed.\n"

        event = event.strip()

        if (event == ""):
            return

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
        devices = Device.objects.filter(user__flightuser__in=users).exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).exclude(user=owner).values_list('deviceToken', flat=True)

        title = "Flight Edited"

        # sendAllNotifications("Flight Edited", body, devices, flightID=flightID)
        send_notifications(devices=devices, title=title, body=body)

    def perform_update(self, serializer):
        self.generate_changelog(serializer)

        serializer.save()

        notificationThread = Thread(target=self.notify_users, args=[])
        notificationThread.start()

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    # def delete(self, request, *args, **kwargs):
    #     return self.destroy(request, *args, **kwargs)

class ValidateFlight(APIView):
    permission_classes = [IsProfessional]

    def notify_user(self, request, flightID):
        f = Flight.objects.get(pk=flightID)
        taxonomy = str(f.species)
        u = f.owner
        devices = u.devices.exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).values_list('deviceToken', flat=True)

        title = "Flight Verified"
        body = f"Your {taxonomy} flight (id {flightID}) has been verified by {self.request.user.username}."

        # sendAllNotifications(title, body, devices, flightID=flightID)
        send_notifications(devices=devices, title=title, body=body)

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
                return HttpResponse("Flight already verified.", status=status.HTTP_200_OK)
            f.validatedBy = request.user.flightuser
            f.save()
            timeOfValidation = timezone.now().replace(microsecond=0)
            f.validatedAt = timeOfValidation
            f.save()

            Changelog.objects.create(user=request.user, flight=f, event=f"Flight verified by {request.user.username}.", date=timeOfValidation)

            notificationThread = Thread(target=self.notify_user, args=[request, pk])
            notificationThread.start()

            return Response("Flight verified.", status=status.HTTP_200_OK)
        except Flight.DoesNotExist:
            return Response("No flight with that id.", status=status.HTTP_404_NOT_FOUND)

class ValidateInvalidateFlight(APIView):
    permission_classes = [IsProfessionalOrReadOnly]

    def notify_user(self, request, flightID, validated):
        f = Flight.objects.get(pk=flightID)
        taxonomy = str(f.species)
        u = f.owner
        devices = u.devices.exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).values_list('deviceToken', flat=True)

        if validated:
            title = "Flight Verified"
            body = f"Your {taxonomy} flight (id {flightID}) has been verified by {self.request.user.username}."
        else:
            title = "Flight Unverified"
            body = f"Your {taxonomy} flight (id {flightID}) has been unverified by {self.request.user.username}."

        # sendAllNotifications(title, body, devices, flightID=flightID)
        send_notifications(devices=devices, title=title, body=body)

    def get(self, request, pk):
        flight = Flight.objects.get(pk=pk)

        if flight.validatedBy:
            username = flight.validatedBy.user.username
        else:
            username = None

        data = {
            "flightID"  : pk,
            "validated" : flight.isValidated(),
            "validatedBy":  username,
            "validatedAt":  flight.validatedAt
        }
        serializer = FlightValidationSerializer(data=data)

        if (serializer.is_valid()):
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, pk):
        serializer = FlightValidationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        flightID = serializer.validated_data["flightID"]

        if flightID != pk:
            return Response({"Errors": "Incorrect flight ID"}, status=status.HTTP_400_BAD_REQUEST)

        flight = Flight.objects.get(pk=pk)

        validate = serializer.validated_data["validate"]

        if validate:
            flight.validatedBy = request.user.flightuser
            timeOfValidation = timezone.now().replace(microsecond=0)
            flight.validatedAt = timeOfValidation

            flight.save()

            Changelog.objects.create(user=request.user, flight=flight, event=f"Flight verified by {request.user.username}.", date=timeOfValidation)

        else:
            flight.validatedBy = None
            flight.validatedAt = None

            flight.save()

            Changelog.objects.create(user=request.user, flight=flight, event=f"Flight unverified by {request.user.username}.", date=timezone.now().replace(microsecond=0))

        notificationThread = Thread(target=self.notify_user, args=[request, pk, validate])
        notificationThread.start()

        if flight.isValidated():
            username = flight.validatedBy.user.username
        else:
            username = None

        data = {
            "flightID"  : pk,
            "validated" : flight.isValidated(),
            "validatedBy":  username,
            "validatedAt":  flight.validatedAt
        }

        responseSerializer = FlightValidationSerializer(data=data)

        if (responseSerializer.is_valid()):
            return Response(responseSerializer.data, status=status.HTTP_200_OK)
        else:
            return Response(responseSerializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
    # pagination_class = BiggerPagesPaginator

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
    # pagination_class = BiggerPagesPaginator

    def get_queryset(self):
        return Genus.objects.all().filter(flightuser=self.request.user.flightuser)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = GenusListSerializer(data=request.data)

        # print("Preparing to update genus list")

        if (serializer.is_valid()):
            genera = serializer.validated_data["genera"]

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
                user.flightuser.genera.remove(genus)

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
        devices = u.devices.exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).values_list('deviceToken', flat=True)

        title = "New Comment"
        body = f"{author.username} has left a new comment on your {taxonomy} flight (id {flightID})."

        # sendAllNotifications(title, body, devices, flightID=flightID)
        send_notifications(devices=devices, title=title, body=body)

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
    alphanumerics = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890:_-"

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

        user_info = FlightUserSerializer(request.user.flightuser, context=self.get_context()).data
        data.update(user_info)

        data["user"] = user_info

        return data

    def getDeviceID(self, request, authToken)->int:
        device = None
        deviceID = 0

        deviceID = self.request.META.get("HTTP_DEVICEID")
        platform = self.request.data.get("platform")
        model = self.request.data.get("model")
        deviceToken = self.request.data.get("deviceToken", "")

        print("Logged in with token: {}".format(deviceToken))

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
                
                if (deviceToken == ""):
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
                print("Create new.")
                print(f"Device ID is now {deviceID}")
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

                print("The device token is {}".format(device.deviceToken))

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
        if (self.request.auth != None):
            print("Authenticated request.")
            # user = self.request.user.flightuser
            # role = user.role.role
            # deviceID = self.request.META['HTTP_DEVICEID']
            print("Got request {}".format(self.request.data))
            device_id = self.request.data.get("deviceID")
            device_token = self.request.data.get("deviceToken")

            if (device_id is None):
                return Response(status=status.HTTP_401_UNAUTHORIZED)

            try:
                device = Device.objects.get(deviceID=device_id)

                device.lastLoggedIn = timezone.now()
                device.active = True
                device.deviceToken = device_token if device_token != None else ""
                device.save()

                user = self.request.user.flightuser

                serializer = FlightUserSerializer(user)

                return Response(serializer.data, status=status.HTTP_200_OK)
            except:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        return Response(status=status.HTTP_401_UNAUTHORIZED)

class CreateUserForm(generic.FormView):
    # In part based on code from 
    # # https://medium.com/@frfahim/django-registration-with-confirmation-email-bb5da011e4ef 
    # by Farhadur Reja Fahim
    form_template = 'nuptiallog/AccountCreateForm.html'
    email_successful = 'nuptiallog/EmailSent.html'
    email_failed = 'nuptiallog/EmailFailed.html'

    def post(self, request, *args, **kwargs):
        form = UserCreationForm(request.POST)
        if (form.is_valid()):
            email_addr = form.cleaned_data["email"]

            if (len(User.objects.all().filter(email=email_addr)) != 0):
                form.errors.update({"email":["A user with that email address already exists"]})
                return render(request, self.form_template, {'form':form})

            professional = form.cleaned_data["professional"]
            institution = form.cleaned_data["institution"]

            username = form.cleaned_data["username"]

            if (len(username) < 6):
                form.errors.update({"username":["Please enter a longer username"]})
                return render(request, self.form_template, {"form":form})

            if (professional and not institution):
                form.errors.update({"institution": ["You must enter your institution"]})
                return render(request, self.form_template, {'form':form})

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
            current_site = get_current_site(request)
            subject = "Activate NuptialTracker Account"
            message = render_to_string('nuptiallog/ActivateEmail.html', {
                'user': user,
                'domain': current_site.domain,
                'uid':  urlsafe_base64_encode(force_bytes(user.pk)),
                'token': accountActivationToken.make_token(user)
            })
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(subject, message, to=[to_email])
            email.content_subtype = 'html'
            # print("Preparing to send e-mail.")
            try:
                email.send()

                # print("Sent e-mail")
                return render(request, 'nuptiallog/EmailSent.html', {'user':user}, status=status.HTTP_201_CREATED)
            except:
                # print("Error sending e-mail.")
                return render(request, self.email_failed, {'user':user}, status=400)
        else:
            return render(request, self.form_template, {'form':form})
    def get(self, request, *args, **kwargs):
        form = UserCreationForm()
        return render(request, self.form_template, {'form':form})


# Password reset based on https://medium.com/@renjithsraj/how-to-reset-password-in-django-bd5e1d6ed652 by Renjith S Raj

class ResetPasswordForm(generic.FormView):
    mobile = False
    form_template = 'nuptiallog/PasswordResetForm.html'
    email_successful = 'nuptiallog/EmailSentPassChange.html'

    def post(self, request, *args, **kwargs):
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            to_email=form.cleaned_data.get('email')
            user = User.objects.get(email=to_email)

            current_site = get_current_site(request)
            subject = "Reset NuptialTracker Password"
            message = render_to_string('nuptiallog/PasswordResetEmail.html', {
                'user': user,
                'domain': current_site.domain,
                'uid':  urlsafe_base64_encode(force_bytes(user.pk)),
                'token': passwordResetToken.make_token(user)
            })
            email = EmailMessage(subject, message, to=[to_email])
            email.content_subtype = 'html'
            # print("Preparing to send e-mail.")
            email.send()

            # print("Sent e-mail")
            return render(request, self.email_successful, {'user':user, 'mobile': self.mobile}, status=status.HTTP_201_CREATED)
        else:
            return render(request, self.form_template, {'form':form, 'mobile': self.mobile})
    def get(self, request, *args, **kwargs):
        form = PasswordResetForm()
        return render(request, self.form_template, {'form':form, 'mobile': self.mobile})

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

class ScientistImageView(APIView):
    def get(self, request, filename):
        # print(filename)
        path = str(MEDIA_ROOT) + "/scientist_pics/" + filename

        if os.path.exists(path):
            imageFile = open(path, 'rb')
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
    serializer_class = FlightSerializer
    ordering_fields = ['flightID', 'dateOfFlight', 'dateRecorded']
    ordering = ['-flightID']

    # queryset = Flight.objects.all()

    # def get_serializer_class(self):
    #     if self.action == "list":
    #         return SimpleFlightSerializer
    #     # return super().get_serializer_class()
    #     return FlightSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticatedOrReadOnly()]
            
        if self.action == 'verify':
            return [IsProfessionalOrReadOnly()]

        return [IsOwnerOrReadOnly()]

    def get_queryset(self):
        queryset = Flight.objects.all()

        max_date = self.request.query_params.get('max_date')
        min_date = self.request.query_params.get('min_date')
        
        genus = self.request.query_params.get('genus')
        species = self.request.query_params.get('species')

        taxonomy_raw: str = self.request.query_params.get('taxonomy')

        location = self.request.query_params.get("loc")

        user_role = self.request.query_params.get("user_role")

        verified = self.request.query_params.get("verified")
        
        has_images = self.request.query_params.get("has_images")

        # max_distance = self.request.query_params.get("within")

        user = self.request.query_params.get('u#ser')

        ordering = self.request.query_params.get('ordering')

        if taxonomy_raw != None:
            taxonomy_list = taxonomy_raw.split(',')
            # taxonomy_list = [entry.replace('+', ' ') for entry in taxonomy_list]
            taxonomy_list = [entry.split(' ', maxsplit=1) for entry in taxonomy_list]

            genera = [entry[0] for entry in taxonomy_list if len(entry) == 1]
            species_list = [Species.objects.get(genus__name=entry[0], name=entry[1]) for entry in taxonomy_list if len(entry) > 1]

            print(genera)
            print(species_list)

            queryset = queryset.filter(Q(genus__name__in=genera) | Q(species__in=species_list))
            # queryset = queryset.filter(species__in=species_list)

        if (user != None):
            queryset = queryset.filter(owner__username=user)

        if (max_date != None):
            queryset = queryset.filter(dateOfFlight__lte=max_date)

        if (min_date != None):
            queryset = queryset.filter(dateOfFlight__gte=min_date)

        # if (genus != None):
        #     queryset = queryset.filter(genus__name=genus)

        #     if (species != None):
        #         queryset = queryset.filter(species__name=species)

        if (user_role != None):
            if user_role == "professional":
                queryset = queryset.filter(owner__flightuser__professional=True, owner__flightuser__flagged=False)
            elif user_role == "enthusiast":
                queryset = queryset.filter(owner__flightuser__professional=False, owner__flightuser__flagged=False)

        if (verified != None):
            if verified == "true":
                queryset = queryset.filter(Q(owner__flightuser__professional=True) & Q(owner__flightuser__flagged=False) | Q(validatedBy__isnull=False))
            elif verified == "false":
                queryset = queryset.exclude(Q(owner__flightuser__professional=True) | Q(validatedBy__isnull=False))

        if has_images != None:
            queryset = queryset.annotate(Count('images'))

            if has_images == "true":
                queryset = queryset.exclude(images__count=0)
            elif has_images == "false":
                queryset = queryset.filter(images__count=0)

        if ordering == None:
            return queryset

        # if (ordering in ["lastUpdated", "-lastUpdated"]):
        #     queryset = queryset.annotate(lastUpdated=F("changes"))

        if (location != None and ordering.lower() in ["location", "-location"]):
            location_split = location.split(',')
            try:
                latitude = float(location_split[0])
                longitude = float(location_split[1])

                reference_point = Point(x=longitude, y=latitude, srid=4326)

                queryset = queryset.annotate(distance=Distance('location', reference_point, spheroid=True))

                if ordering.lower() == "location":
                    queryset = queryset.order_by('distance')
                else:
                    queryset = queryset.order_by('-distance')

                # if (max_distance != None):
                #     try:
                #         max_distance_float = float(max_distance)
                #         queryset = queryset.filter(location__distance_lte=(reference_point, D(max_distance_float)))
                #     except ValueError:
                #         pass

                for f in queryset:
                    print("Flight {}: Distance is {}".format(f.flightID, f.distance))

                return queryset

            except ValueError:
                pass

        if (ordering.lower() in ["location", "-location"]):
            raise BadLocationUrlException

        queryset = filters.OrderingFilter().filter_queryset(self.request, queryset, self)
        return queryset

    def generate_notification_body_creation(self, flight):
        return f"A new {flight.genus.name} {flight.species.name} flight (id {flight.flightID}) has been recorded by {flight.owner.username}."

    def notify_users_flight_creation(self, flight):
        body = self.generate_notification_body_creation(flight)
        species = flight.species
        species_users = species.flightuser_set.all()
        genus = flight.genus
        genus_users = genus.flightuser_set.all()
        species_devices = Device.objects.filter(user__flightuser__in=species_users).exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).exclude(user=flight.owner).values_list('deviceToken', flat=True)
        genus_devices = Device.objects.filter(user__flightuser__in=genus_users).exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).exclude(user=flight.owner).values_list('deviceToken', flat=True)

        devices = genus_devices.union(species_devices)


        title = "Flight Created"

        # sendAllNotifications("Flight Created", body, devices, flightID=flight.flightID)
        send_notifications(devices=devices, title=title, body=body)

    def list(self, request, format=None):
        queryset = self.get_queryset()
        # sorted_queryset = filters.OrderingFilter().filter_queryset(request, queryset, self)
        serializer = SimpleFlightSerializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, format=None):
        serializer = FlightSerializerBarebones(data=self.request.data)
        user = self.request.user
        date = timezone.now().replace(microsecond=0)

        if not serializer.is_valid():
            return Response({"error":"Invalid formatting"}, status=status.HTTP_400_BAD_REQUEST)

        # print(serializer.validated_data)
        #genusName = serializer.validated_data["genus"]["name"]
        # genus = Genus.objects.get(name=genusName)
        genusName = serializer.validated_data["species"]["genus"]["name"]
        genus = Genus.objects.get(name=genusName)
        speciesName = serializer.validated_data["species"]["name"]
        species = Species.objects.get(genus=genus, name=speciesName)
        flight = serializer.save(owner=self.request.user, genus=genus, species=species, dateRecorded=date)

        weatherThread = Thread(target=get_weather_for_flight, args=(flight, ))

        weatherThread.start()

        notificationThread = Thread(target=self.notify_users_flight_creation, args=[flight])
        notificationThread.start()

        #getWeatherForFlight(flight)
        event = "Flight created."

        Changelog.objects.create(user=user, date=date, flight=flight, event=event)

        return Response(FlightSerializer(instance=flight).data, status=status.HTTP_201_CREATED)

    def generate_changelog(self, serializer):
        # print("Starting changelog")
        flight = self.get_object()
        user = self.request.user
        date = timezone.now().replace(microsecond=0)

        event = ""
        #hasChanged=False

        genus_name = serializer.validated_data["species"]["genus"]["name"]
        new_genus = Genus.objects.get(name=genus_name)
        new_species = Species.objects.get(genus=new_genus, name=serializer.validated_data["species"]["name"])
        new_confidence = serializer.validated_data["confidence"]
        new_latitude = serializer.validated_data["latitude"]
        new_longitude = serializer.validated_data["longitude"]
        new_radius = serializer.validated_data["radius"]
        new_date_of_flight = serializer.validated_data["dateOfFlight"]
        new_size = serializer.validated_data["size"]
        new_image = None
        removed_image = False
    
        if (serializer.validated_data["hasImage"]):
            try:
                new_image = serializer.validated_data["image"]
            except:
                new_image = None
        else:
            if flight.image:
                flight.image.delete()
                removed_image = True
            new_image = None

        if (new_genus != flight.genus):
            event += f"- Genus changed from {flight.genus} to {new_genus}\n"
        if (new_species != flight.species):
            event += f"- Species changed from {flight.species} to {new_species}\n"
        if (new_confidence != flight.confidence):
            confidence_levels = ["low", "high"]

            new_level = confidence_levels[new_confidence]
            old_level = confidence_levels[flight.confidence]
            event += f"- Confidence changed from {old_level} to {new_level}\n"
        if (new_latitude != flight.latitude or new_longitude != flight.longitude):
            event += f"- Location changed from ({round(flight.latitude,3)}, {round(flight.longitude, 3)}) to ({round(new_latitude, 3)}, {round(new_longitude, 3)})\n"
        if (new_radius != flight.radius):
            event += f"- Radius changed from {round(flight.radius, 1)} km to {round(new_radius, 1)} km\n"
        if (new_date_of_flight != flight.dateOfFlight):
            old_date_string = flight.dateOfFlight.strftime("%I:%M %p %Z on %d %b %Y")
            new_date_string = new_date_of_flight.strftime("%I:%M %p %Z on %d %b %Y")
            event += f"- Date of flight changed from {old_date_string} to {new_date_string}\n"
        if (new_size != flight.size):
            event += f"- Size of flight changed from {flight.size} to {new_size}\n"
        if new_image:
            event += "- Image changed.\n"
        if removed_image:
            event += "- Image Removed.\n"

        event = event.rstrip()

        Changelog.objects.create(user=user, flight=flight, event=event, date=date)
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
        users = species.flightuser_set.all()
        genus = flight.genus
        users = users.union(genus.flightuser_set.all())
        devices = Device.objects.filter(user__flightuser__in=users).exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).exclude(user=owner).values_list('deviceToken', flat=True)

        title = "Flight Edited"

        # sendAllNotifications("Flight Edited", body, devices, flightID=flight_id)
        send_notifications(devices=devices, title=title, body=body)

    def update(self, request, pk=None, format=None):
        print("Making serializer")
        serializer = FlightSerializer(data=self.request.data)
        print("Made serializer")

        if not serializer.is_valid():
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        self.generate_changelog(serializer)

        print("Saving serializer")
        flight = self.get_object()
        instance = serializer.update(flight, serializer.validated_data)
        # instance = serializer.save()
        print("Saved serializer")

        notificationThread = Thread(target=self.notify_users_update, args=[])
        notificationThread.start()

        return Response(serializer.data, status=status.HTTP_200_OK)

    def notify_user_verify(self, request, flightID, validated):
        f = Flight.objects.get(pk=flightID)
        taxonomy = str(f.species)
        u = f.owner
        devices = u.devices.exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).values_list('deviceToken', flat=True)

        if validated:
            title = "Flight Verified"
            body = f"Your {taxonomy} flight (id {flightID}) has been verified by {self.request.user.username}."
        else:
            title = "Flight Unverified"
            body = f"Your {taxonomy} flight (id {flightID}) has been unverified by {self.request.user.username}."

        # sendAllNotifications(title, body, devices, flightID=flightID)
        send_notifications(devices=devices, title=title, body=body)

    @action(detail=True, methods=['GET'])
    def verify(self, request, pk=None, format=None):
        flight = Flight.objects.get(pk=pk)

        if flight.validatedBy:
            username = flight.validatedBy.user.username
        else:
            username = None

        data = {
            "flightID"  : pk,
            "validated" : flight.isValidated(),
            "validatedBy":  username,
            "validatedAt":  flight.validatedAt
        }
        serializer = FlightValidationSerializer(data=data)

        if (serializer.is_valid()):
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @verify.mapping.post
    def verify_flight(self, request, pk=None, format=None):
        serializer = FlightValidationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # flightID = int(serializer.validated_data["flightID"])

        # if flightID != pk:
        #     return Response({"Errors": "Incorrect flight ID"}, status=status.HTTP_400_BAD_REQUEST)

        flight = Flight.objects.get(pk=pk)

        validate = serializer.validated_data["validate"]

        if validate:
            flight.validatedBy = request.user.flightuser
            timeOfValidation = timezone.now().replace(microsecond=0)
            flight.validatedAt = timeOfValidation

            flight.save()

            Changelog.objects.create(user=request.user, flight=flight, event=f"Flight verified by {request.user.username}.", date=timeOfValidation)

        else:
            flight.validatedBy = None
            flight.validatedAt = None

            flight.save()

            Changelog.objects.create(user=request.user, flight=flight, event=f"Flight unverified by {request.user.username}.", date=timezone.now().replace(microsecond=0))

        notificationThread = Thread(target=self.notify_user_verify, args=[request, pk, validate])
        notificationThread.start()

        if flight.isValidated():
            username = flight.validatedBy.user.username
        else:
            username = None

        data = {
            "flightID"  : pk,
            "validated" : flight.isValidated(),
            "validatedBy":  username,
            "validatedAt":  flight.validatedAt
        }

        responseSerializer = FlightValidationSerializer(data=data)

        if (responseSerializer.is_valid()):
            return Response(responseSerializer.data, status=status.HTTP_200_OK)
        else:
            return Response(responseSerializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True)
    def history(self, request, pk=None, format=None):
        flight = get_object_or_404(Flight.objects.all(), flightID=pk)
        changelog_entries = Changelog.objects.all().filter(flight=flight).order_by('-date')
        serializer = ChangelogSerializer(changelog_entries, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True)
    def weather(self, request, pk=None, format=None):
        weather = get_object_or_404(Weather.objects.all(), flight_id=pk)
        serializer = WeatherSerializer(weather)

        return Response(serializer.data, status=status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):

    serializer_class = CommentSerializer
    # permission_classes = [IsOwnerOrReadOnly]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        if self.action not in ["list", "retrieve"]:
            return [IsAuthorOrReadOnly()]
        return []

    def get_queryset(self):
        return Comment.objects.filter(responseTo__flightID=self.kwargs['flight_pk'])

    def notify_user_comment(self, author, flight):
        flightID = flight.flightID
        taxonomy = str(flight.species)
        u = flight.owner
        devices = u.devices.exclude(deviceToken='').exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now()).values_list('deviceToken', flat=True)

        title = "New Comment"
        body = f"{author.username} has left a new comment on your {taxonomy} flight (id {flightID})."

        # sendAllNotifications(title, body, devices, flightID=flightID)
        send_notifications(devices=devices, title=title, body=body)

    def create(self, request, *args, **kwargs):
        # print(serializer.validated_data)
        #author = User.objects.get(username=serializer.validated_data["author"])
        serializer = CommentSerializer(data=self.request.data)
        if not serializer.is_valid():
            return Response(status=status.HTTP_400_BAD_REQUEST)
            
        text = serializer.validated_data["text"]
        # flightID = serializer.validated_data["responseTo"]["flightID"]
        flight_id = self.kwargs['flight_pk']
        responseTo = Flight.objects.get(pk=flight_id)
        author = self.request.user
        time = timezone.now().replace(microsecond=0) #serializer.validated_data["time"]

        comment = Comment.objects.create(author=author, text=text, responseTo=responseTo, time=time)

        if (author != responseTo.owner):
            notificationThread = Thread(target=self.notify_user_comment, args=[author, responseTo])
            notificationThread.start()

        return Response(CommentSerializer(instance=comment).data, status=status.HTTP_201_CREATED)



class FlightImageViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin):

    parser_classes = [ImageUploadParser]
    serializer_class = FlightImageSerializer
    # permission_classes = [IsOwnerOrReadOnly]

    def get_permissions(self):
        if self.action == "create":
            return [IsFlightOwnerOrReadOnly(self.kwargs['flight_pk'])]

        return [IsImageOwnerOrReadOnly()]

    def get_queryset(self):
        return FlightImage.objects.filter(flight__flightID=self.kwargs['flight_pk'])

    # def notify_user_comment(self, author, flight):
    #     flightID = flight.flightID
    #     taxonomy = str(flight.species)
    #     u = flight.owner
    #     devices = u.devices.exclude(deviceToken=None).exclude(authToken=None).exclude(authToken__expiry__lte=timezone.now())

    #     title = "New Comment"
    #     body = f"{author.username} has left a new comment on your {taxonomy} flight (id {flightID})."

    #     sendAllNotifications(title, body, devices, flightID=flightID)

    def create(self, request, *args, **kwargs):
        image = self.request.data['file']
        created_by = self.request.user
        date_created = timezone.now().replace(microsecond=0)
        flight = Flight.objects.get(pk=self.kwargs['flight_pk'])

        try:
            pil_image = Image.open(image)
            pil_image.verify()
        except:
            raise ParseError("Incorrect file type provided.")

        flight_image = FlightImage.objects.create(image=image, created_by=created_by, date_created=date_created, flight=flight)
        flight_image.save()

        serializer = FlightImageSerializer(instance=flight_image)

        changelog_text = "-Added Image"
        changelog_entry = Changelog.objects.create(flight=flight, event=changelog_text, date=date_created, user=created_by)
        # changelog_entry.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        image_id = self.get_object().id
        flight = self.get_object().flight
        destroy_response = super().destroy(request, *args, **kwargs)

        changelog_text = "-Removed image {}".format(image_id)

        changelog_entry = Changelog.objects.create(flight=flight, event=changelog_text, date=timezone.now().replace(microsecond=0), user=self.request.user)
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

def scientificAdvisoryBoard(request):
    scientists = ScientificAdvisor.objects.all()

    return render(request, 'nuptiallog/ScientificAdvisoryBoard.html', {"scientists": scientists})

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
    allFlights = Flight.objects.order_by('-flightID')
    
    end = start + offset

    show_next = end <= len(allFlights) + 1
    show_prev = start - offset >= 0

    flights = allFlights[start: end]

    return render(request, 'nuptiallog/Browse.html', {"flights": flights, "next_start":end, "offset":offset, "prev_start":start-offset, "show_next": show_next, "show_prev": show_prev})