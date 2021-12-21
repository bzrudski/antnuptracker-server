#
#  models.py
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

# from django.db import models
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from knox.models import AuthToken
from random import randint
from django.db.models import signals
from django.utils import timezone
#from drf_extra_fields import fields
# Create your models here.

# Create your models here.
class Flight(models.Model):
    owner = models.ForeignKey('auth.User', related_name='flights', on_delete=models.CASCADE, null=True)
    flightID = models.AutoField(primary_key=True)
    genus = models.ForeignKey('Genus', on_delete=models.PROTECT, null=True)
    species = models.ForeignKey('Species', on_delete=models.PROTECT, null=True)
    dateOfFlight = models.DateTimeField('date of flight')
    dateRecorded = models.DateTimeField('date recorded')
    latitude = models.FloatField()#max_digits=11,decimal_places=8)
    longitude = models.FloatField()#max_digits=11,decimal_places=8)
    location = models.PointField(blank=True, null=True, default=None)
    radius = models.FloatField('radius of location approximation (km)', default=0.0)

    SIZE_OPTIONS = [
        (0, "Many queens"),
        (1, "One queen")
    ]
    size = models.IntegerField("size of flight", choices=SIZE_OPTIONS, default=1)

    CONFIDENCE_CHOICES = [
        (0, "Low"),
        (1, "High"),
    ]
    confidence = models.IntegerField('Species confidence level', choices=CONFIDENCE_CHOICES, null=True, blank=True)
    image = models.ImageField(upload_to='flight_pics', null=True, blank=True)

    validatedBy = models.ForeignKey('FlightUser', related_name='validatedFlights', on_delete=models.SET_NULL, blank=True, null=True)
    validatedAt = models.DateTimeField('date of validation', null=True, blank=True)

    def isValidated(self):
        """
        Determine if a flight has been validated. Flights are implicitly validated
        if created by a professional. Otherwise, a flight is considered validated
        if a professional has verified it.
        """
        return (self.owner.flightuser.professional and not self.owner.flightuser.flagged) or (self.validatedBy != None and not self.validatedBy.flagged)

    def flightStatus(self)->int:
        if self.owner.flightuser.flagged:
            return -1
        elif self.owner.flightuser.professional or self.isValidated():
            return 1
        else:
            return 0
    
    def __str__(self):
        return f"{self.genus} {self.species} ({self.flightID})"

    def hasWeather(self)->bool:
        try:
            self.weather
            return True
        except:
            return False

    def hasImageFile(self)->bool:
        return bool(self.image)

    def getLastUpdated(self):
        return self.changes.order_by('-date').first().date

    def get_confidence_string(self):
        if self.confidence == 0:
            return "low"
        else:
            return "high"

    def get_size_string(self):
        if self.size == 0:
            return "many queens"
        else:
            return "single queen"

    def get_location_string(self):
        latCoord = 'N' if self.latitude > 0 else 'S'
        lonCoord = 'E' if self.longitude > 0 else 'W'

        return f"({self.latitude:.3f}\u00b0{latCoord}, {self.longitude:.2f}\u00b0{lonCoord})"

class FlightImage(models.Model):
    flight = models.ForeignKey('Flight', on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to="flight_pics/")
    created_by = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    date_created = models.DateTimeField()

class Comment(models.Model):
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    text = models.TextField()
    time = models.DateTimeField()
    responseTo = models.ForeignKey('Flight', on_delete=models.CASCADE, related_name="comments")

class Changelog(models.Model):
    user = models.ForeignKey('auth.User', related_name='changes', on_delete=models.PROTECT)
    flight = models.ForeignKey('Flight', related_name='changes', on_delete=models.PROTECT)
    event = models.TextField()
    date = models.DateTimeField()

class Genus(models.Model):
    name = models.CharField(max_length=32)

    def __str__(self):
        return self.name

class Species(models.Model):
    name = models.CharField(max_length=50)
    genus = models.ForeignKey('Genus', on_delete=models.CASCADE, related_name='species')

    def __str__(self):
        return self.genus.name + " " + self.name


class Role(models.Model):
    role = models.CharField(max_length=30)

    def __str__(self):
        return self.role

    @staticmethod
    def generateChoices():
        choices = []

        for role in Role.objects.all():
            choices.append((role.id, role.role))

        return choices

class FlightUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    # role = models.ForeignKey('Role', on_delete=models.SET_NULL, null=True)
    professional = models.BooleanField(default=False)
    institution = models.CharField(max_length=80, blank=True)
    genera = models.ManyToManyField('Genus', blank=True)
    species = models.ManyToManyField('Species', blank=True)
    description = models.TextField('Public description', blank=True)
    flagged = models.BooleanField(default=False)

    def flag(self):
        self.flagged = True
        self.user.is_active = False
        self.user.save()
        self.save()

    def unflag(self):
        self.flagged = False
        self.user.is_active = True
        self.user.save()
        self.save()

    def status(self):
        if self.flagged:
            return -1
        elif self.professional:
            return 1
        else:
            return 0

def create_flightUser(sender, instance, created, **kwargs):
    if (created):
        FlightUser.objects.create(user=instance)

signals.post_save.connect(create_flightUser, sender=User, weak=False, dispatch_uid='models.create_flightUser')

class Device(models.Model):
    deviceID = models.BigIntegerField('Device ID', default=0, primary_key=True)
    user = models.ForeignKey('auth.User', related_name='devices', on_delete=models.CASCADE, blank=True)
    OS_CHOICES = [
        ('IOS', 'iOS'),
        ('ANDROID', 'Android'),
        ('WINDOWS', 'Windows'),
        ('MACOS', 'macOS'),
        ('LINUX', 'Linux'),
        ('FUCHSIA', 'Fuchsia'),
    ]
    platform = models.CharField(max_length=10, choices=OS_CHOICES)
    model = models.CharField(max_length=64)
    deviceToken = models.CharField(max_length=200, blank=True, default="")
    authToken = models.OneToOneField(AuthToken, on_delete=models.SET_NULL, null=True, blank=True)
    lastLoggedIn = models.DateTimeField('last logged in')
    active = models.BooleanField(default=True)

    def logout(self):
        self.active = False

    @staticmethod
    def get_all_ids():
        return Device.objects.values_list('deviceID', flat=True)

    @staticmethod
    def generate_new_id():
        newID = randint(1, 2**32)
        currentIDs = Device.get_all_ids()
        while (newID in currentIDs):
            newID = randint(1, 2**32)
        return newID

def logout_device(sender, instance, **kwargs):
    try:
        device = instance.device
        device.active = False
        device.save()
    except:
        try:
            device = sender.device
            device.active = False
            device.save()
        except Exception as error:
            print("Logout error:")
            print(error)
            # print(error)
            return

signals.pre_delete.connect(logout_device, sender=AuthToken, weak=False, dispatch_uid='models.logout_device')

class WeatherDescription(models.Model):
    desc = models.CharField('description', max_length=64, blank=True, default="")
    longDesc = models.CharField('full description', max_length=128, blank=True, default="")

class BasicWeatherData(models.Model):
    temperature = models.FloatField(default=0)
    pressure = models.FloatField(default=0)
    pressureSea = models.FloatField('sea level pressure',default=0, null=True)
    pressureGround = models.FloatField('ground pressure',default=0, null=True)
    humidity = models.IntegerField(default=0)
    tempMin = models.FloatField('min temp', default=0, null=True)
    tempMax = models.FloatField('max temp', default=0, null=True)
    clouds = models.IntegerField(default=0)

class DayInfo(models.Model):
    sunrise = models.DateTimeField(default=timezone.now)
    sunset = models.DateTimeField(default=timezone.now)

class WindInfo(models.Model):
    windSpeed = models.FloatField('speed', default=0, null=True)
    windDegree = models.IntegerField('direction', default=0, null=True)

class RainInfo(models.Model):
    rain1 = models.FloatField('rain 1 hour', default=0, null=True)
    rain3 = models.FloatField('rain 3 hour', default=0, null=True)

class Weather(models.Model):
    flight = models.OneToOneField('Flight', on_delete=models.SET_NULL, null=True)

    description = models.OneToOneField('WeatherDescription', on_delete=models.CASCADE, null=True)
    weather = models.OneToOneField('BasicWeatherData', on_delete=models.CASCADE, null=True)
    day = models.OneToOneField('DayInfo', on_delete=models.CASCADE, null=True)
    rain = models.OneToOneField('RainInfo', on_delete=models.CASCADE, blank=True, null=True)
    wind = models.OneToOneField('WindInfo', on_delete=models.CASCADE, blank=True, null=True)

    timeFetched = models.DateTimeField(default=timezone.now)

class ScientificAdvisor(models.Model):
    name = models.CharField(max_length=75)
    position = models.CharField(max_length=125)
    image = models.ImageField(upload_to="scientist_pics")
    url = models.URLField(blank=True)

class Taxonomy(models.Model):
    version = models.BigAutoField(primary_key=True)
    updated = models.DateTimeField()
    genera = models.ManyToManyField('Genus')
    species = models.ManyToManyField('Species')