#
#  urls.py
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

from django.urls import path, include
from django.conf.urls import url
from rest_framework.urlpatterns import format_suffix_patterns
from .pandasViews import FlightDataExport
from . import views

urlpatterns = [
    path('', views.welcome, name="home"),
    # To deprecate... See below at API. Keeping for now because client app relies on hardcoded urls
    path('download/', views.download, name="download"),
    path('flights/', views.FlightList.as_view()),
    path('flights/<int:pk>/', views.FlightDetail.as_view()),
    path('flights/<int:pk>/history/', views.ChangelogForFlight.as_view()),
    path('flights/<int:pk>/weather/', views.WeatherForFlight.as_view()),
    path('flights/<int:pk>/validate/', views.ValidateFlight.as_view()),
    path('flights/download', FlightDataExport.as_view()),
    path('flights/download-json', views.FlightListNested.as_view()),
    path('my-flights/', views.MyFlightsList.as_view()),
    path('my-species/', views.MySpeciesList.as_view()),
    path('genera/', views.GenusListView.as_view()),
    path('genera/<str:genus>/', views.SpeciesDetailView.as_view()),
    path('media/flight_pics/<str:filename>', views.ImageView.as_view()),
    path('users/', views.UserListView.as_view()),
    path('users/<str:username>/', views.UserDetailView.as_view()),
    path('comments/', views.CommentList.as_view()),
    # Migrate over to have api in the url to separate from the rest of the site
    path('api/flights/', views.FlightList.as_view()),
    path('api/flights/<int:pk>/', views.FlightDetail.as_view()),
    path('api/flights/<int:pk>/history/', views.ChangelogForFlight.as_view()),
    path('api/flights/<int:pk>/weather/', views.WeatherForFlight.as_view()),
    path('api/flights/<int:pk>/validate/', views.ValidateFlight.as_view()),
    path('api/flights/download', FlightDataExport.as_view(), name='downloadview'),
    path('api/flights/download-json', views.FlightListNested.as_view(), name='nestedjson'),
    path('api/my-flights/', views.MyFlightsList.as_view()),
    path('api/my-species/', views.MySpeciesList.as_view()),
    path('api/genera/', views.GenusListView.as_view()),
    path('api/genera/<str:genus>/', views.SpeciesDetailView.as_view()),
    path('api/media/flight_pics/<str:filename>', views.ImageView.as_view()),
    path('api/users/', views.UserListView.as_view()),
    path('api/users/<str:username>/', views.UserDetailView.as_view()),
    path('api/comments/', views.CommentList.as_view()),
    # Non-api views, frontend for website
    path('create-account/', views.CreateUserForm.as_view(), name="create-account"),
    path('reset-password/', views.ResetPasswordForm.as_view(), name="reset-password"),
    path('activate/<str:uidb64>/<str:token>/', views.UserActivationView.as_view(), name="activate"),
    path('passchange/<str:uidb64>/<str:token>/', views.ChangePasswordForm.as_view(), name="changepass"),
    path('community-standards/', views.communityStandards, name="community_standards"),
    path('about/', views.about, name="about"),
    path('scientific-advisory-board/', views.scientificAdvisoryBoard, name="scientificAdvisoryBoard"),
    path('media/scientist_pics/<str:filename>', views.ScientistImageView.as_view()),
    path('help/', views.helpView, name="help"),
    path('privacy-policy/', views.privacy, name="privacy"),
    path('terms-and-conditions/', views.terms, name="terms"),
    path('taxonomy/', views.taxonomy, name="taxonomy"),
    path('browse/', views.browse, {"start": 0, "offset": 15}, name="browse"),
    path('browse?start=<int:start>&offset=<int:offset>', views.browse, name="browse_params"),
    path('app-license/', views.applicense, name="applicense"),
    path('server-license/', views.serverlicense, name="serverlicense"),
    # path('user_management/', include('django.contrib.auth.urls')),
]

urlpatterns = format_suffix_patterns(urlpatterns)
