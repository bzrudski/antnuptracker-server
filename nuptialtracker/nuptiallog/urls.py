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
from .views import FlightList, FlightDetail, GenusListView, SpeciesDetailView, ImageView, UserListView, CommentList, ChangelogForFlight, CreateUserForm, UserActivationView, ResetPasswordForm, ChangePasswordForm, WeatherForFlight, MyFlightsList, MySpeciesList, UpdateMySpeciesList, welcome, download, UserDetailView, communityStandards, about, helpView, ValidateFlight, FlightListNested, browse, terms, privacy, applicense, serverlicense, taxonomy
from .pandasViews import FlightDataExport

urlpatterns = [
    path('', welcome, name="home"),
    path('download/', download, name="download"),
    path('flights/', FlightList.as_view()),
    path('flights/<int:pk>/', FlightDetail.as_view()),
    path('flights/<int:pk>/history/', ChangelogForFlight.as_view()),
    path('flights/<int:pk>/weather/', WeatherForFlight.as_view()),
    path('flights/<int:pk>/validate/', ValidateFlight.as_view()),
    path('flights/download', FlightDataExport.as_view(), name='downloadview'),
    path('flights/download-json', FlightListNested.as_view(), name='nestedjson'),
    path('my-flights/', MyFlightsList.as_view()),
    path('my-species/', MySpeciesList.as_view()),
    path('genera/', GenusListView.as_view()),
    path('genera/<str:genus>/', SpeciesDetailView.as_view()),
    path('flights/flight_pics/<str:filename>', ImageView.as_view()),
    path('users/', UserListView.as_view()),
    path('users/<str:username>/', UserDetailView.as_view()),
    path('comments/', CommentList.as_view()),
    path('create-account/', CreateUserForm.as_view(), name="create-account"),
    path('reset-password/', ResetPasswordForm.as_view(), name="reset-password"),
    path('activate/<str:uidb64>/<str:token>/', UserActivationView.as_view(), name="activate"),
    path('passchange/<str:uidb64>/<str:token>/', ChangePasswordForm.as_view(), name="changepass"),
    path('community-standards/', communityStandards, name="community_standards"),
    path('about/', about, name="about"),
    path('help/', helpView, name="help"),
    path('privacy-policy/', privacy, name="privacy"),
    path('terms-and-conditions/', terms, name="terms"),
    path('taxonomy/', taxonomy, name="taxonomy"),
    path('browse/', browse, {"start": 0, "offset": 15}, name="browse"),
    path('browse?start=<int:start>&offset=<int:offset>', browse, name="browse_params"),
    path('app-license/', applicense, name="applicense"),
    path('server-license/', serverlicense, name="serverlicense"),
    # path('user_management/', include('django.contrib.auth.urls')),
]

urlpatterns = format_suffix_patterns(urlpatterns)
