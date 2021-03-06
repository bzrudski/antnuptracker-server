#
#  serializers.py
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

from rest_framework import serializers
from .models import Flight, Comment, FlightUser, Changelog, Weather, WeatherDescription, BasicWeatherData, DayInfo, WindInfo,RainInfo, Role, Genus, Species
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth import password_validation
from drf_extra_fields.fields import Base64ImageField
from django.utils.timezone import datetime

# Define flight serializer
class GenusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genus
        fields = ['name']

class SpeciesSerializer(serializers.ModelSerializer):
    genus = GenusSerializer()
    class Meta:
        model = Species
        fields = ['genus','name']

class CommentSerializer(serializers.ModelSerializer):
    flight = serializers.IntegerField(source="responseTo.flightID")
    author = serializers.ReadOnlyField(source="author.username")
    role = serializers.ReadOnlyField(source="author.flightuser.status")
    time = serializers.ReadOnlyField()

    class Meta:
        model = Comment
        fields = ('flight', 'author', 'role', 'text', 'time')

class FlightSerializer(serializers.ModelSerializer):
    taxonomy = SpeciesSerializer(source='species')
    comments = CommentSerializer(many=True, read_only=True)
    owner = serializers.ReadOnlyField(source="owner.username")
    ownerRole = serializers.ReadOnlyField(source='owner.flightuser.status')

    # TO DEPRECATE THESE TWO FIELS... REPLACED BY `ownerRole`
    ownerProfessional = serializers.BooleanField(source="owner.flightuser.professional", read_only=True)
    ownerFlagged = serializers.BooleanField(source="owner.flightuser.flagged", read_only=True)
    # END OF DEPRECATION COMMENT

    validated = serializers.BooleanField(source="isValidated", read_only=True)
    validatedBy = serializers.ReadOnlyField(source="validatedBy.user.username", allow_null=True)
    hasImage = serializers.BooleanField(write_only=True, required=False, default=False)
    image = Base64ImageField(required=False)

    weather = serializers.BooleanField(source='hasWeather', read_only=True)

    def update(self, instance, validated_data):
        instance.genus = Genus.objects.get(name=validated_data["species"]["genus"]["name"])
        instance.species = Species.objects.get(genus=instance.genus, name=validated_data["species"]["name"])
        instance.confidence = validated_data.get("confidence", instance.confidence)
        instance.latitude = validated_data.get("latitude", instance.latitude)
        instance.longitude = validated_data.get("longitude", instance.longitude)
        instance.radius = validated_data.get("radius", instance.radius)
        instance.dateOfFlight = validated_data.get("dateOfFlight", instance.dateOfFlight)
        instance.size = validated_data.get("size", instance.size)

        old_image = instance.image

        try:
            if not validated_data["hasImage"]:
                instance.image = None
                # print("No image")

            elif validated_data["image"] == None:
                instance.image = old_image
                # print("Old image")

            else:
                instance.image = validated_data["image"]
                # print("New image")
        except:
            instance.image=old_image
            # print("All else failed... old image")

        instance.save()

        return instance

    class Meta:
        model = Flight
        fields = ('flightID', 'taxonomy','latitude', 'longitude', 'radius', 'dateOfFlight', 'owner', 'ownerRole', 'ownerProfessional', 'ownerFlagged', 'dateRecorded', 'weather', 'comments', 'hasImage', 'image', 'confidence', 'size', 'validated', 'validatedBy', 'validatedAt')
        read_only_fields = ('dateRecorded', 'validatedAt')

class FlightSerializerBarebones(serializers.ModelSerializer):
    taxonomy = SpeciesSerializer(source='species')
    owner = serializers.CharField(source="owner.username")
    validated = serializers.BooleanField(source="isValidated", read_only=True)
    ownerRole = serializers.ReadOnlyField(source='owner.flightuser.status')
    lastUpdated = serializers.ReadOnlyField(source='getLastUpdated')
    image = Base64ImageField(required=False, write_only=True)

    class Meta:
        model = Flight
        fields = ('flightID', 'taxonomy', 'owner', 'ownerRole', 'latitude', 'longitude','radius', 'dateOfFlight', 'dateRecorded', 'image', 'confidence', 'size', 'lastUpdated', 'validated')
        extra_kwargs = {
            'radius': {'write_only': True},
            'dateRecorded': {'write_only':  True},
            'comments': {'write_only':  True},
            'image': {'write_only':  True},
            'confidence': {'write_only':  True},
            'size' : {'write_only': True},
            }
        # ordering = ['-dateRecorded']

class SpeciesListSerializer(serializers.Serializer):
    species = SpeciesSerializer(many=True, write_only=True)

    def validate_species(self, value):
        validatedSpecies = []

        for entry in value:
            genusName = entry["genus"]["name"]
            speciesName = entry["name"]

            genus = Genus.objects.get(name=genusName)
            species = Species.objects.get(genus=genus, name=speciesName)

            validatedSpecies.append(species)

        # print(validatedSpecies)
        return validatedSpecies

class GenusListSerializer(serializers.Serializer):
    genera = GenusSerializer(many=True, write_only=True)

    def validate_genera(self, value):
        validatedGenera = []

        for entry in value:
            genusName = entry["name"]

            genus = Genus.objects.get(name=genusName)

            validatedGenera.append(genus)

        # print(validatedGenera)
        return validatedGenera

class FlightValidationSerializer(serializers.Serializer):
    flightID = serializers.IntegerField()
    validate = serializers.BooleanField(required=False)
    validated = serializers.BooleanField(write_only=True, required=False)
    validatedBy = serializers.CharField(write_only=True, required=False, allow_null=True)
    validatedAt = serializers.DateTimeField(write_only=True, required=False, allow_null=True)

class FlightUserSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = FlightUser
        fields = ('username', 'professional', 'description', 'institution', 'flagged')

class UserSerializer(serializers.ModelSerializer):
    def validate_password(self, password):
        password_validation.validate_password(password)
        return password

    class Meta:
        model = User
        fields = ('username', 'password', 'professional', 'email')
        write_only_fields = ('password', 'professional')

class ChangelogSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = Changelog
        fields = ('user','date','event')

class WeatherDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherDescription
        exclude = ['id']

class BasicWeatherSerializer(serializers.ModelSerializer):
    class Meta:
        model = BasicWeatherData
        exclude = ['id']

class DayInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayInfo
        exclude = ['id']

class WindSerializer(serializers.ModelSerializer):
    class Meta:
        model = WindInfo
        exclude = ['id']

class RainSerializer(serializers.ModelSerializer):
    class Meta:
        model = RainInfo
        exclude = ['id']

class WeatherSerializer(serializers.ModelSerializer):
    flightID = serializers.IntegerField(source='flight_id')
    description = WeatherDescriptionSerializer()
    weather = BasicWeatherSerializer()
    day = DayInfoSerializer()
    rain = RainSerializer()
    wind = WindSerializer()

    class Meta:
        model = Weather
        fields = ('flightID','description', 'weather', 'day', 'rain', 'wind','timeFetched')

class DayInfoSerializerExport(serializers.ModelSerializer):
    sunrise = serializers.ReadOnlyField()
    sunset = serializers.ReadOnlyField()

    class Meta:
        model = DayInfo
        fields = ('sunrise', 'sunset')

class FlatWeatherSerializer(serializers.ModelSerializer):
    description = WeatherDescriptionSerializer()
    weather = BasicWeatherSerializer()
    day = DayInfoSerializerExport()
    rain = RainSerializer()
    wind = WindSerializer()
    time_weather_fetched = serializers.ReadOnlyField(source="timeFetched")

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # newRep = {}

        description = rep.pop('description')
        weather = rep.pop('weather')
        day = rep.pop('day')
        rain = rep.pop('rain')
        wind = rep.pop('wind')
        # timeFetched = rep.pop('timeFetched')

        for key in description:
            rep[key] = description[key]

        for key in weather:
            rep[key] = weather[key]

        for key in day:
            rep[key] = day[key]

        if rain != None:
            for key in rain:
                rep[key] = rain[key]
        else:
            rep['rain1'] = None
            rep['rain3'] = None

        if wind != None:
            for key in wind:
                rep[key] = wind[key]
        else:
            rep['windSpeed'] = None
            rep['windDegree'] = None

        # rep['time_weather_fetched'] = timeFetched

        return rep

    def validate_time_fetched(self, val):
        return val.replace(tzinfo=None)

    class Meta:
        model = Weather
        fields = ('description', 'weather', 'day', 'rain', 'wind','time_weather_fetched')

class FlightSerializerExport(serializers.ModelSerializer):
    # taxonomy = SpeciesSerializer(source='species')
    date_of_flight = serializers.ReadOnlyField(source="dateOfFlight", allow_null=False)
    genus = serializers.CharField(source='species.genus.name')
    species = serializers.CharField(source='species.name')
    comments = CommentSerializer(many=True, read_only=True)
    reported_by = serializers.ReadOnlyField(source="owner.username")
    date_recorded = serializers.ReadOnlyField(source="dateRecorded", allow_null=False)
    user_professional = serializers.BooleanField(source="owner.flightuser.professional", read_only=True)
    user_flagged = serializers.BooleanField(source="owner.flightuser.flagged", read_only=True)
    validated = serializers.BooleanField(source="isValidated", read_only=True)
    validated_by = serializers.ReadOnlyField(source="validatedBy.username", allow_null=True)
    validated_at = serializers.ReadOnlyField(source="validatedAt", allow_null=True)
    image = Base64ImageField(required=False)
    weather = FlatWeatherSerializer()

    confidence_level = serializers.CharField(source="get_confidence_string")
    flight_size = serializers.CharField(source="get_size_string")
    
    def validate_date_of_flight(self, val):
        return val.replace(tzinfo=None)

    def validate_validated_at(self, val):
        return val.replace(tzinfo=None)

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        weather = rep.pop('weather')
        comments = rep.pop('comments')

        if weather:
            for key in weather:
                rep[key] = weather[key]

        i = 0

        for comment in comments:
            for key in comment:
                if key == "flight":
                    continue

                rep[f"{key}_{i}"] = comment[key]
            
            i += 1

        for key in rep:
            val = rep[key]

            # print(f"Examining key {key} with value {val}")

            if isinstance(val, datetime):
                rep[key] = val.replace(tzinfo=None)

        return rep

    class Meta:
        model = Flight
        fields = ('flightID', 'genus', 'species', 'confidence_level', 'date_of_flight', 'latitude','longitude', 'flight_size', 'reported_by', 'user_professional', 'user_flagged', 'date_recorded', 'validated', 'validated_by', 'validated_at', 'weather', 'comments', 'image')

class FlightSerializerFull(serializers.ModelSerializer):
    genus = serializers.CharField(source='species.genus.name')
    species = serializers.CharField(source='species.name')
    comments = CommentSerializer(many=True, read_only=True)
    reported_by = serializers.ReadOnlyField(source="owner.username")
    user_professional = serializers.BooleanField(source="owner.flightuser.professional", read_only=True)
    user_flagged = serializers.BooleanField(source="owner.flightuser.flagged", read_only=True)
    validated = serializers.BooleanField(source="isValidated", read_only=True)
    validated_by = serializers.ReadOnlyField(source="validatedBy.username", allow_null=True)
    validated_at = serializers.ReadOnlyField(source="validatedAt", allow_null=True)
    image = Base64ImageField(required=False)
    weather = WeatherSerializer()
    confidence_level = serializers.CharField(source="get_confidence_string")
    flight_size = serializers.CharField(source="get_size_string")

    class Meta:
        model = Flight
        fields = ('flightID', 'genus', 'species', 'confidence_level', 'dateOfFlight', 'latitude','longitude', 'flight_size', 'reported_by', 'user_professional', 'user_flagged', 'dateRecorded', 'validated', 'validated_by', 'validated_at', 'weather', 'comments', 'image')

# class FlightSerializerAllNested(serializers)