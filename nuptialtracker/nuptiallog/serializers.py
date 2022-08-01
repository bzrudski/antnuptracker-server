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

# from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth import password_validation
from django.contrib.gis.geos.point import Point
from django.utils.timezone import datetime
from rest_framework import serializers
# from drf_extra_fields.fields import Base64ImageField
from .models import Flight, Comment, FlightImage, FlightUser, Changelog, Taxonomy, Weather, WeatherDescription, BasicWeatherData, DayInfo, WindInfo, RainInfo, Role, Genus, Species

# Define flight serializer
class GenusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genus
        fields = ['name']

class SpeciesSerializer(serializers.ModelSerializer):
    genus = GenusSerializer()
    class Meta:
        model = Species
        fields = ['genus', 'name']


class GenusNameIdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genus
        fields = ['id', 'name']


class NewSpeciesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = ["id", "name", "genus"]


class NewGenusSerializer(serializers.ModelSerializer):
    # species = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    species = NewSpeciesSerializer(many=True, read_only=True)

    class Meta:
        model = Genus
        fields = ['id', 'name', 'species']

class SpeciesNameIdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Species
        fields = ['id', 'name']

class FullTaxonomySerializer(serializers.ModelSerializer):
    # species = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    species = SpeciesNameIdSerializer(many=True, read_only=True)

    class Meta:
        model = Genus
        fields = ['id', 'name', 'species']

class IdOnlySpeciesSerializer(serializers.Serializer):
    # class Meta:
    #     model = Species
    #     fields = ['id']

    id = serializers.IntegerField()

    def validate_id(self, value):
        if len(Species.objects.filter(pk = value)) > 0:
            return value
        raise serializers.ValidationError("Invalid species id")


class IdOnlyGenusSerializer(serializers.Serializer):
    id = serializers.IntegerField()

    # class Meta:
    #     model = Genus
    #     fields = ['id']

    def validate_id(self, value):
        if len(Genus.objects.filter(pk = value)) > 0:
            return value
        raise serializers.ValidationError("Invalid genus id")

class CommentSerializer(serializers.ModelSerializer):
    flight = serializers.ReadOnlyField(source="responseTo.flightID")
    author = serializers.ReadOnlyField(source="author.username")
    role = serializers.ReadOnlyField(source="author.flightuser.status")
    time = serializers.ReadOnlyField()

    class Meta:
        model = Comment
        fields = ('id', 'flight', 'author', 'role', 'text', 'time')

class FlightSerializer(serializers.ModelSerializer):
    # taxonomy = SpeciesSerializer(source='species')
    taxonomy = serializers.IntegerField(source='species.id') #NewSpeciesSerializer(source='species')
    comments = CommentSerializer(many=True, read_only=True, required=False)
    owner = serializers.ReadOnlyField(source="owner.username")
    ownerRole = serializers.ReadOnlyField(source='owner.flightuser.status')

    latitude = serializers.FloatField(source='location.y')
    longitude = serializers.FloatField(source='location.x')

    validated = serializers.BooleanField(source="isValidated", read_only=True)
    validatedBy = serializers.ReadOnlyField(source="validatedBy.user.username", allow_null=True)
    hasImage = serializers.BooleanField(write_only=True, required=False, default=False)
    # image = Base64ImageField(required=False)

    weather = serializers.BooleanField(source='hasWeather', read_only=True)

    def update(self, instance, validated_data):

        new_species = Species.objects.get(pk=validated_data["species"]["id"])
        new_genus = new_species.genus

        instance.genus = new_genus
        instance.species = new_species

        # instance.genus = Genus.objects.get(name=validated_data["species"]["genus"]["name"])
        # instance.species = Species.objects.get(genus=instance.genus, name=validated_data["species"]["name"])
        instance.confidence = validated_data.get("confidence", instance.confidence)
        
        new_location = validated_data.get("location", None)

        if new_location is not None:
            # latitude = validated_data.get("latitude", instance.location.y)
            # longitude = validated_data.get("longitude", instance.location.x)
            latitude = new_location["y"]
            longitude = new_location["x"]
            instance.location = Point(longitude, latitude, srid=4326)
        
        # ************ PREPARE TO DEPRECATE **************** #
        instance.latitude = latitude
        instance.longitude = longitude
        # ************ PREPARE TO DEPRECATE **************** #

        instance.radius = validated_data.get("radius", instance.radius)
        instance.dateOfFlight = validated_data.get("dateOfFlight", instance.dateOfFlight)
        instance.size = validated_data.get("size", instance.size)

        old_image = instance.image

        try:
            if not validated_data["hasImage"]:
                instance.image = None
                # print("No image")

            elif validated_data["image"] is None:
                instance.image = old_image
                # print("Old image")

            else:
                instance.image = validated_data["image"]
                # print("New image")
        except:
            instance.image = old_image
            # print("All else failed... old image")

        # print("Saving instance...")
        instance.save()
        # print("Saved instance")

        return instance

    class Meta:
        model = Flight
        fields = ('flightID', 'taxonomy', 'latitude', 'longitude', 'radius', 'dateOfFlight', 'owner', 'ownerRole', 'dateRecorded', 'weather', 'comments', 'hasImage', 'image', 'confidence', 'size', 'validated', 'validatedBy', 'validatedAt')
        read_only_fields = ('dateRecorded', 'validatedAt')
        extra_kwargs = {
            'dateRecorded': {'required': False},
            'owner': {'required': False},
            'flightID': {'required': False},
        }

class FlightSerializerBarebones(serializers.ModelSerializer):
    taxonomy = serializers.IntegerField(source='species.id') #SpeciesSerializer(source='species')
    owner = serializers.ReadOnlyField(source="owner.username")
    validated = serializers.BooleanField(source="isValidated", read_only=True)
    ownerRole = serializers.ReadOnlyField(source='owner.flightuser.status')
    lastUpdated = serializers.ReadOnlyField(source='getLastUpdated')
    # image = Base64ImageField(required=False, write_only=True)

    latitude = serializers.FloatField(source='location.y')
    longitude = serializers.FloatField(source='location.x')

    class Meta:
        model = Flight
        fields = ('flightID', 'taxonomy', 'owner', 'ownerRole', 'latitude', 'longitude', 'radius', 'dateOfFlight', 'image', 'confidence', 'size', 'lastUpdated', 'validated') #, 'dateRecorded',
        extra_kwargs = {
            'radius': {'write_only': True},
            # 'dateRecorded': {'write_only':  True},
            'comments': {'write_only':  True},
            'image': {'write_only':  True},
            'confidence': {'write_only':  True},
            'size' : {'write_only': True},
            }
        # ordering = ['-dateRecorded']

class SimpleFlightSerializer(serializers.ModelSerializer):
    lastUpdated = serializers.ReadOnlyField(source='getLastUpdated')

    class Meta:
        model = Flight
        fields = ('flightID', 'lastUpdated')

class FlightImageSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source='created_by.username')
    class Meta:
        model = FlightImage
        fields = '__all__'

class SpeciesListSerializer(serializers.Serializer):
    species = IdOnlySpeciesSerializer(many=True)

    def validate_species(self, value):
        validated_species = []

        for entry in value:
            # genus_name = entry["genus"]["name"]
            # species_name = entry["name"]

            # genus = Genus.objects.get(name=genus_name)
            species = Species.objects.get(pk=entry['id'])

            validated_species.append(species)

        # print(validatedSpecies)
        return validated_species

class GenusListSerializer(serializers.Serializer):
    genera = IdOnlyGenusSerializer(many=True)

    # def validate_genera(self, value):
    #     validated_genera = []

    #     print(value)

    #     for entry in value:
    #         genus = Genus.objects.get(pk=entry["id"])
    #         # genus_name = entry["name"]

    #         # genus = Genus.objects.get(name=genus_name)

    #         validated_genera.append(genus)

    #     # print(validatedGenera)
    #     return validated_genera

class FlightValidationSerializer(serializers.Serializer):
    flightID = serializers.IntegerField(read_only=True)
    validate = serializers.BooleanField(required=False)
    validated = serializers.BooleanField(write_only=True, required=False)
    validatedBy = serializers.CharField(write_only=True, required=False, allow_null=True)
    validatedAt = serializers.DateTimeField(write_only=True, required=False, allow_null=True)

class FlightUserSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")
    professional = serializers.ReadOnlyField()
    flagged = serializers.ReadOnlyField()

    class Meta:
        model = FlightUser
        fields = ('username', 'professional', 'description', 'institution', 'flagged')


class UserSerializer(serializers.ModelSerializer):
    def validate_password(self, password):
        password_validation.validate_password(password)
        return password

    class Meta:
        model = get_user_model()
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

        if rain is not None:
            for key in rain:
                rep[key] = rain[key]
        else:
            rep['rain1'] = None
            rep['rain3'] = None

        if wind is not None:
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

    latitude = serializers.FloatField(source='location.y')
    longitude = serializers.FloatField(source='location.x')

    comments = CommentSerializer(many=True, read_only=True)
    reported_by = serializers.ReadOnlyField(source="owner.username")
    date_recorded = serializers.ReadOnlyField(source="dateRecorded", allow_null=False)
    user_professional = serializers.BooleanField(source="owner.flightuser.professional", read_only=True)
    user_flagged = serializers.BooleanField(source="owner.flightuser.flagged", read_only=True)
    validated = serializers.BooleanField(source="isValidated", read_only=True)
    validated_by = serializers.ReadOnlyField(source="validatedBy.username", allow_null=True)
    validated_at = serializers.ReadOnlyField(source="validatedAt", allow_null=True)
    # image = Base64ImageField(required=False)
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
        fields = ('flightID', 'genus', 'species', 'confidence_level', 'date_of_flight', 'latitude', 'longitude', 'flight_size', 'reported_by', 'user_professional', 'user_flagged', 'date_recorded', 'validated', 'validated_by', 'validated_at', 'weather', 'comments', 'image')

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
    # image = Base64ImageField(required=False)
    weather = WeatherSerializer()
    confidence_level = serializers.CharField(source="get_confidence_string")
    flight_size = serializers.CharField(source="get_size_string")
    latitude = serializers.FloatField(source='location.y')
    longitude = serializers.FloatField(source='location.x')

    class Meta:
        model = Flight
        fields = ('flightID', 'genus', 'species', 'confidence_level', 'dateOfFlight', 'latitude', 'longitude', 'flight_size', 'reported_by', 'user_professional', 'user_flagged', 'dateRecorded', 'validated', 'validated_by', 'validated_at', 'weather', 'comments', 'image')

# class FlightSerializerAllNested(serializers)

class TaxonomyVersionSerializer(serializers.ModelSerializer):
    genus_count = serializers.ReadOnlyField(source="genera.count")
    species_count = serializers.ReadOnlyField(source="species.count")

    class Meta:
        model = Taxonomy
        fields = ['version', 'genus_count', 'species_count']
