#
#  weather.py
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

import requests
import json
from .models import Weather, Flight, WeatherDescription, BasicWeatherData, DayInfo, WindInfo, RainInfo
from django.utils import timezone
import datetime
import os

def generateURLforCoordinates(lat, lon):
    API_KEY = os.getenv("WEATHERKEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&APPID={API_KEY}"
    return url

def generateURLforCoordinatesOneCall(lat, lon, time):
    API_KEY = os.getenv("WEATHERKEY")
    epoch = datetime.datetime.utcfromtimestamp(0)
    timeSinceEpoch = int((time - epoch).total_seconds())
    # print("Time since epoch: " + str(timeSinceEpoch))
    url = f"https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={lat}&lon={lon}&dt={timeSinceEpoch}&units=metric&appid={API_KEY}"
    # print(url)
    return url

def getWeatherForLocation(lat, lon, old=False, time=None):
    if old:
        url = generateURLforCoordinatesOneCall(lat, lon, time)
    else:
        url = generateURLforCoordinates(lat, lon)
    response = requests.get(url)
    return response.json()

def parseHistoricalWeatherData(weatherData, time, flight):
    basicWeatherData = weatherData['current']
    utcoffset = datetime.timedelta(seconds=int(weatherData['timezone_offset']))

    temp = basicWeatherData['temp']
    pressure = basicWeatherData['pressure']
    humidity = basicWeatherData['humidity']
    clouds = basicWeatherData['clouds']

    basicWeather = BasicWeatherData.objects.create(
        temperature=temp,
        pressure=pressure,
        pressureSea=None,
        pressureGround=None,
        humidity=humidity,
        clouds=clouds,
        tempMin=None,
        tempMax=None
    )

    windSpeed = basicWeatherData.get('wind_speed')
    windDegree = basicWeatherData.get('wind_deg')

    if windSpeed or windDegree:
        wind = WindInfo.objects.create(
            windSpeed=windSpeed,
            windDegree=windDegree
        )
    else:
        wind = None

    try:
        rainRaw = weatherData['rain']
        rain1 = rainRaw.get('1h')
        rain3 = rainRaw.get('3h')

        if rain1 or rain3:
            rain = RainInfo.objects.create(rain1=rain1, rain3=rain3)
        else:
            rain = None
    except:
        rain = None

    sunrise = timezone.datetime.fromtimestamp(basicWeatherData['sunrise']) + utcoffset
    sunset = timezone.datetime.fromtimestamp(basicWeatherData['sunset']) + utcoffset

    day = DayInfo.objects.create(
        sunrise=sunrise,
        sunset=sunset
    )

    desc = ""
    longDesc = ""

    for entry in basicWeatherData['weather']:
        desc += entry['main'] + "\n"
        longDesc += entry['description'] + "\n"

    desc = desc.strip()
    longDesc = longDesc.strip()

    description = WeatherDescription.objects.create(
        desc=desc,
        longDesc=longDesc
    )

    timeFetched = time.replace(tzinfo=None, microsecond=0) + utcoffset

    weather = Weather.objects.create(
        flight=flight,
        description=description,
        weather=basicWeather,
        day=day,
        rain=rain,
        wind=wind,
        timeFetched=timeFetched
    )

    return weather

def parseCurrentWeatherData(weatherData, time, flight):
    weatherDescriptions = weatherData['weather']
    desc = ""
    longDesc = ""

    i=-1

    for i in range(0, len(weatherDescriptions)-2):
        desc += weatherDescriptions[i]['main'] + "\n"
        longDesc += weatherDescriptions[i]['description'] + "\n"

    i += 1

    desc += weatherDescriptions[i]['main']
    longDesc += weatherDescriptions[i]['description']

    description = WeatherDescription.objects.create(desc=desc, longDesc=longDesc)

    basicWeather = weatherData['main']
    temperature = basicWeather['temp']
    pressure = basicWeather['pressure']
    humidity = basicWeather['humidity']
    tempMin = basicWeather['temp_min']
    tempMax = basicWeather['temp_max']

    try:
        clouds = weatherData['clouds']['all']
    except KeyError:
        clouds = 0

    try:
        pressureSea = basicWeather['sea_level']
    except KeyError:
        pressureSea = None

    try:
        pressureGround = basicWeather['grnd_level']
    except KeyError:
        pressureGround = None

    weatherInfo = BasicWeatherData.objects.create(
        temperature=temperature,
        pressure=pressure,
        humidity=humidity,
        tempMin=tempMin,
        tempMax=tempMax,
        pressureSea=pressureSea,
        pressureGround=pressureGround,
        clouds=clouds
    )

    try:
        windInfoRaw = weatherData["wind"]
        try:
            windSpeed = windInfoRaw['speed']
        except KeyError:
            windSpeed = 0

        try:
            windDegree = windInfoRaw['deg']
        except:
            windDegree = 0
        wind = WindInfo.objects.create(windSpeed=windSpeed, windDegree=windDegree)

    except:
        wind = None

    utcoffset = timezone.timedelta(seconds=int(weatherData["timezone"]))

    sunrise = timezone.datetime.fromtimestamp(weatherData['sys']['sunrise']) + utcoffset
    sunset = timezone.datetime.fromtimestamp(weatherData['sys']['sunset']) + utcoffset
    timeFetched = timezone.now().replace(tzinfo=None, microsecond=0) + utcoffset

    day = DayInfo.objects.create(sunrise=sunrise, sunset=sunset)

    try:
        rainRaw = weatherData['rain']
        try:
            rain1 = rainRaw['1h']
        except:
            rain1 = None

        try:
            rain3 = rainRaw['3h']
        except:
            rain3 = None

        rain = RainInfo.objects.create(rain1=rain1, rain3=rain3)
    except:
        rain = None

    # print("Got all variables")

    weather = Weather.objects.create(
        flight=flight,
        description=description,
        weather=weatherInfo,
        day=day,
        rain=rain,
        wind=wind,
        timeFetched=timeFetched
    )

def getWeatherForFlight(flight):
    dateOfFlight = flight.dateOfFlight
    dateNow = timezone.now()

    # print("Got times")


    if ((dateNow - dateOfFlight) > timezone.timedelta(days=5)):
        return None

    lat = round(flight.latitude, 3)
    lon = round(flight.longitude, 3)
    # print("Got location")

    old = (dateNow-dateOfFlight > timezone.timedelta(hours=5))

    # rawDate = (dateOfFlight - dateOfFlight.utcoffset()).replace(tzinfo=None)

    weatherData = getWeatherForLocation(lat, lon, old=old, time=dateOfFlight)
    # print(weatherData)

    if old:
        weather = parseHistoricalWeatherData(weatherData, dateNow, flight)
    else:
        weather = parseCurrentWeatherData(weatherData, dateNow, flight)

    # print(weather)
    # print("Weather created")

    return weather

# TODO: - Create Queue Perhaps to not violate number of requests

# class LocationQueue:
#     def __init__(self, locations=[]):
#         self.locations = locations

#     def enqueue(self, location):
#         self.locations.append(location)

#     def dequeue(self):
#         return self.locations.pop(index=0)

class FlightQueue:
    def __init__(self, flights=[]):
        self.flights = flights

    def enqueue(self, flight):
        self.flights.append(flight)

    def dequeue(self):
        return self.flights.pop(index=0)

    def isEmpty(self):
        return len(self.flights) == 0

# def getWeatherForTop(queue):
#         lat, lon = queue.dequeue()
#         weatherJSON = getWeatherForLocation(lat, lon)
#         Weather.objects.create()

class WeatherManagement:
    flights = FlightQueue()
    numberOfCallsPerMinute = 0
    MAX_CALLS = 59

    def getWeatherForFlights(self):
        for flight in self.flights:
            lat = flight.latitude
            lon = flight.longitude

            weather = getWeatherForLocation(lat, lon)