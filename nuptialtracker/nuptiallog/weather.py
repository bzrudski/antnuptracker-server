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

# import json
import requests
from .models import Weather, Flight, WeatherDescription, BasicWeatherData, DayInfo, WindInfo, RainInfo
from django.utils import timezone
import datetime
import os

def generate_url_coord(lat, lon):
    API_KEY = os.getenv("WEATHERKEY")
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&APPID={API_KEY}"
    return url

def generate_url_one_call_coord(lat, lon, time):
    API_KEY = os.getenv("WEATHERKEY")
    epoch = timezone.datetime.utcfromtimestamp(0).replace(tzinfo=timezone.utc)
    # epoch = timezone.now()
    time_in_utc = time.astimezone(tz=timezone.utc)
    time_since_epoch = int((time_in_utc - epoch).total_seconds())
    # print("Time since epoch: " + str(time_since_epoch))
    url = f"https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={lat}&lon={lon}&dt={time_since_epoch}&units=metric&appid={API_KEY}"
    # print(url)
    return url

def get_weather_for_location(lat, lon, old=False, time=None):
    if old:
        url = generate_url_one_call_coord(lat, lon, time)
    else:
        url = generate_url_coord(lat, lon)
    response = requests.get(url)
    return response.json()

def parse_historical_weather(weather_data, time, flight):
    basic_weather_data = weather_data['current']
    # utcoffset = timezone.timedelta(seconds=int(weather_data['timezone_offset']))
    tz = timezone.utc

    temp = basic_weather_data['temp']
    pressure = basic_weather_data['pressure']
    humidity = basic_weather_data['humidity']
    clouds = basic_weather_data['clouds']

    basic_weather = BasicWeatherData.objects.create(
        temperature=temp,
        pressure=pressure,
        pressureSea=None,
        pressureGround=None,
        humidity=humidity,
        clouds=clouds,
        tempMin=None,
        tempMax=None
    )

    wind_speed = basic_weather_data.get('wind_speed')
    wind_degree = basic_weather_data.get('wind_deg')

    if wind_speed or wind_degree:
        wind = WindInfo.objects.create(
            windSpeed=wind_speed,
            windDegree=wind_degree
        )
    else:
        wind = None

    try:
        rain_raw = weather_data['rain']
        rain1 = rain_raw.get('1h')
        rain3 = rain_raw.get('3h')

        if rain1 or rain3:
            rain = RainInfo.objects.create(rain1=rain1, rain3=rain3)
        else:
            rain = None
    except KeyError:
        rain = None

    sunrise = timezone.datetime.fromtimestamp(basic_weather_data['sunrise']).replace(tzinfo=tz)# + utcoffset
    sunset = timezone.datetime.fromtimestamp(basic_weather_data['sunset']).replace(tzinfo=tz) #+ utcoffset

    day = DayInfo.objects.create(
        sunrise=sunrise,
        sunset=sunset
    )

    desc = ""
    long_desc = ""

    for entry in basic_weather_data['weather']:
        desc += entry['main'] + "\n"
        long_desc += entry['description'] + "\n"

    desc = desc.strip()
    long_desc = long_desc.strip()

    description = WeatherDescription.objects.create(
        desc=desc,
        longDesc=long_desc
    )

    # tz = timezone.timezone(offset=utcoffset)

    # time_fetched = time.replace(microsecond=0) + utcoffset
    time_fetched = time.replace(microsecond=0, tzinfo=tz)

    weather = Weather.objects.create(
        flight=flight,
        description=description,
        weather=basic_weather,
        day=day,
        rain=rain,
        wind=wind,
        timeFetched=time_fetched
    )

    return weather

def parse_current_weather(weather_data, time, flight):
    weather_descriptions = weather_data['weather']
    desc = ""
    long_desc = ""

    i = -1

    for i in range(0, len(weather_descriptions)-2):
        desc += weather_descriptions[i]['main'] + "\n"
        long_desc += weather_descriptions[i]['description'] + "\n"

    i += 1

    desc += weather_descriptions[i]['main']
    long_desc += weather_descriptions[i]['description']

    description = WeatherDescription.objects.create(desc=desc, longDesc=long_desc)

    basic_weather = weather_data['main']
    temperature = basic_weather['temp']
    pressure = basic_weather['pressure']
    humidity = basic_weather['humidity']
    temp_min = basic_weather['temp_min']
    temp_max = basic_weather['temp_max']

    try:
        clouds = weather_data['clouds']['all']
    except KeyError:
        clouds = 0

    pressure_sea = basic_weather.get('sea_level')
    pressure_ground = basic_weather.get('grnd_level')
    
    # try:
    #     pressure_sea = basic_weather['sea_level']
    # except KeyError:
    #     pressure_sea = None

    # try:
    #     pressure_ground = basic_weather['grnd_level']
    # except KeyError:
    #     pressure_ground = None

    weather_info = BasicWeatherData.objects.create(
        temperature=temperature,
        pressure=pressure,
        humidity=humidity,
        tempMin=temp_min,
        tempMax=temp_max,
        pressureSea=pressure_sea,
        pressureGround=pressure_ground,
        clouds=clouds
    )

    try:
        wind_info_raw = weather_data["wind"]
        wind_speed = wind_info_raw.get("speed", 0)
        wind_degree = wind_info_raw.get("deg", 0)

        # try:
        #     wind_speed = wind_info_raw['speed']
        # except KeyError:
        #     wind_speed = 0

        # try:
        #     wind_degree = wind_info_raw['deg']
        # except:
        #     wind_degree = 0
        wind = WindInfo.objects.create(windSpeed=wind_speed, windDegree=wind_degree)

    except KeyError:
        wind = None

    utc_offset = timezone.timedelta(seconds=int(weather_data["timezone"]))

    # tz = datetime.timezone(offset=utc_offset)
    tz = timezone.utc

    # sunrise = timezone.datetime.fromtimestamp(weather_data['sys']['sunrise']) + utc_offset
    # sunset = timezone.datetime.fromtimestamp(weather_data['sys']['sunset']) + utc_offset
    # time_fetched = timezone.now().replace(microsecond=0) + utc_offset

    sunrise = timezone.datetime.fromtimestamp(weather_data['sys']['sunrise']).replace(tzinfo=tz)
    sunset = timezone.datetime.fromtimestamp(weather_data['sys']['sunset']).replace(tzinfo=tz)
    time_fetched = timezone.now().replace(microsecond=0, tzinfo=tz)

    day = DayInfo.objects.create(sunrise=sunrise, sunset=sunset)

    try:
        rain_raw = weather_data['rain']
        rain1 = rain_raw.get('1h')
        rain3 = rain_raw.get('3h')
        
        rain = RainInfo.objects.create(rain1=rain1, rain3=rain3)
        
        # try:
        #     rain1 = rain_raw['1h']
        # except KeyError:
        #     rain1 = None

        # try:
        #     rain3 = rain_raw['3h']
        # except KeyError:
        #     rain3 = None

    except KeyError:
        rain = None

    # print("Got all variables")

    weather = Weather.objects.create(
        flight=flight,
        description=description,
        weather=weather_info,
        day=day,
        rain=rain,
        wind=wind,
        timeFetched=time_fetched
    )

    return weather

def get_weather_for_flight(flight):
    date_of_flight = flight.dateOfFlight
    current_time = timezone.now()

    # print("Got times")


    if (current_time - date_of_flight) > timezone.timedelta(days=5):
        return None

    lat = round(flight.latitude, 3)
    lon = round(flight.longitude, 3)
    # print("Got location")

    old = (current_time-date_of_flight > timezone.timedelta(minutes=30))

    # rawDate = (dateOfFlight - dateOfFlight.utcoffset()).replace(tzinfo=None)

    weather_data = get_weather_for_location(lat, lon, old=old, time=date_of_flight)
    # print(weatherData)

    if old:
        print("Retrieved historical weather for flight {}.".format(flight.flightID))
        print(weather_data)
        print("The current time is {} and the time of flight is {}".format(current_time, date_of_flight))
        weather = parse_historical_weather(weather_data, current_time, flight)
    else:
        print("Retrieved current weather for flight {}.".format(flight.flightID))
        print(weather_data)
        weather = parse_current_weather(weather_data, current_time, flight)

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

# class FlightQueue:
#     def __init__(self, flights=None):
#         if flights is not None:
#             self.flights = flights
#         else:
#             self.flights = []

#     def enqueue(self, flight):
#         self.flights.append(flight)

#     def dequeue(self):
#         return self.flights.pop(index=0)

#     def isEmpty(self):
#         return len(self.flights) == 0

# def getWeatherForTop(queue):
#         lat, lon = queue.dequeue()
#         weatherJSON = getWeatherForLocation(lat, lon)
#         Weather.objects.create()

# class WeatherManagement:
#     flights = FlightQueue()
#     numberOfCallsPerMinute = 0
#     MAX_CALLS = 59

#     def getWeatherForFlights(self):
#         for flight in self.flights:
#             lat = flight.latitude
#             lon = flight.longitude

#             weather = get_weather_for_location(lat, lon)
