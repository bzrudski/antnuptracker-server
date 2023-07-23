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

from django.urls import path, include, re_path
# from django.conf.urls import re_path
from rest_framework.urlpatterns import format_suffix_patterns
# from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .pandasViews import FlightDataExport
from . import views

DEVELOPMENT_MODE = False

urlpatterns = [
    path('', views.welcome, name="home", kwargs={"update_development":DEVELOPMENT_MODE}),
    # To deprecate... See below at API. Keeping for now because client app relies on hardcoded urls
    path('download/', views.download, name="download", kwargs={"update_development":DEVELOPMENT_MODE}),
    # path('flights/', views.FlightList.as_view()),
    # path('flights/<int:pk>/', views.FlightDetail.as_view()),
    # path('flights/<int:pk>/history/', views.ChangelogForFlight.as_view()),
    # path('flights/<int:pk>/weather/', views.WeatherForFlight.as_view()),
    # path('flights/<int:pk>/validate/', views.ValidateFlight.as_view()),
    path('flights/download', FlightDataExport.as_view()),
    path('flights/download-json', views.FlightListNested.as_view()),
    path('my-flights/', views.MyFlightsList.as_view()),
    path('my-species/', views.MySpeciesList.as_view()),
    path('genera/', views.GenusListView.as_view()),
    path('genera/<str:genus>/', views.SpeciesDetailView.as_view()),
    path('latest-taxonomy/', views.TaxonomyView.as_view()),
    path('media/flight_pics/<str:filename>', views.ImageView.as_view()),
    # path('users/', views.UserListView.as_view()),
    path('users/<str:username>/', views.UserDetailView.as_view()),
    # path('comments/', views.CommentList.as_view()),
    # Migrate over to have api in the url to separate from the rest of the site
    # path('api/flights/', views.FlightList.as_view()),
    # path('api/flights/<int:pk>/', views.FlightDetail.as_view()),
    # path('api/flights/<int:pk>/history/', views.ChangelogForFlight.as_view()),
    # path('api/flights/<int:pk>/weather/', views.WeatherForFlight.as_view()),
    # path('api/flights/<int:pk>/validate/', views.ValidateFlight.as_view()),
    # path('api/flights/<int:pk>/validate-flight/', views.ValidateInvalidateFlight.as_view()),
    path('api/flights/download', FlightDataExport.as_view(), name='downloadview'),
    path('api/flights/download-json', views.FlightListNested.as_view(), name='nestedjson'),
    path('api/my-flights/', views.MyFlightsList.as_view()),
    path('api/my-species/', views.MySpeciesList.as_view()),
    path('api/my-genera/', views.MyGenusList.as_view()),
    # path('api/genera/', views.GenusListView.as_view()),
    # path('api/genera/<str:genus>/', views.SpeciesDetailView.as_view()),
    path('api/taxonomy/', views.FullTaxonomyView.as_view()),
    path('api/latest-taxonomy/', views.TaxonomyView.as_view()),
    path('api/media/flight_pics/<str:filename>', views.ImageView.as_view()),
    # path('api/users/', views.UserListView.as_view()),
    path('api/users/<str:username>/', views.UserDetailView.as_view()),
    # path('api/comments/', views.CommentList.as_view()),
    # Non-api views, frontend for website
    path('create-account/', views.CreateUserForm.as_view(), name="create-account", kwargs={"update_development":DEVELOPMENT_MODE}),
    path('reset-password/', views.ResetPasswordForm.as_view(), name="reset-password", kwargs={"update_development":DEVELOPMENT_MODE}),
    path('activate/<str:uidb64>/<str:token>/', views.UserActivationView.as_view(), name="activate"),
    path('passchange/<str:uidb64>/<str:token>/', views.ChangePasswordForm.as_view(), name="changepass"),
    path('community-standards/', views.communityStandards, name="community_standards", kwargs={"update_development":DEVELOPMENT_MODE}),
    path('about/', views.about, name="about", kwargs={"update_development":DEVELOPMENT_MODE}),
    # path('scientific-advisory-board/', views.scientificAdvisoryBoard, name="scientificAdvisoryBoard"),
    # path('media/scientist_pics/<str:filename>', views.ScientistImageView.as_view()),
    path('help/', views.helpView, name="help", kwargs={"update_development":DEVELOPMENT_MODE}),
    path('privacy-policy/', views.privacy, name="privacy", kwargs={"update_development":DEVELOPMENT_MODE}),
    path('terms-and-conditions/', views.terms, name="terms", kwargs={"update_development":DEVELOPMENT_MODE}),
    path('taxonomy/', views.taxonomy, name="taxonomy", kwargs={"update_development":DEVELOPMENT_MODE}),
    # path('browse/', views.browse, {"start": 0, "offset": 15, "update_development": update_development}, name="browse"),
    # path('browse?start=<int:start>&offset=<int:offset>', views.browse, name="browse_params", kwargs={"update_development":update_development}),
    path('app-license/', views.applicense, name="applicense"),
    path('server-license/', views.serverlicense, name="serverlicense"),
    path('api/taxonomy-version/', views.TaxonomyVersionView.as_view(), name="taxonomy-version"),
    # path('user_management/', include('django.contrib.auth.urls')),
]

flights_router = routers.DefaultRouter()
flights_router.register(r'flights', views.FlightViewSet, basename="flights")

comments_router = routers.NestedDefaultRouter(flights_router, r'flights', lookup='flight')
comments_router.register(r'comments', views.CommentViewSet, basename='flight-comments')

images_router = routers.NestedDefaultRouter(flights_router, r'flights', lookup='flight')
images_router.register(r'images', views.FlightImageViewSet, basename='flight-images')

genera_router = routers.DefaultRouter()
genera_router.register(r'genera', views.GenusViewSet, basename="genera")

species_router = routers.NestedDefaultRouter(genera_router, r'genera', lookup="genus")
species_router.register(r'species', views.SpeciesViewSet, basename='species')

urlpatterns = format_suffix_patterns(urlpatterns)

urlpatterns += [re_path(r'^api/', include(flights_router.urls))]
urlpatterns += [re_path(r'^api/', include(comments_router.urls))]
urlpatterns += [re_path(r'^api/', include(images_router.urls))]
urlpatterns += [re_path(r'^api/', include(genera_router.urls))]
urlpatterns += [re_path(r'^api/', include(species_router.urls))]
