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

"""nuptialtracker URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from knox import views as knoxViews
from nuptiallog.views import LoginView, VerifyTokenView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('nuptiallog.urls')),
    path('api-auth',include('rest_framework.urls')),
    path('login/', LoginView.as_view()),
    path('login/verify/', VerifyTokenView.as_view()),
    path('logoutall/', knoxViews.LogoutAllView.as_view()),
    path('logout/', knoxViews.LogoutView.as_view())
    # url(r'^login/?', LoginView.as_view()),
    # url(r'^login/verify/?', VerifyTokenView.as_view()),
    # url(r'^logoutall/?', knoxViews.LogoutAllView.as_view()),
    # url(r'^logout/?', knoxViews.LogoutView.as_view())
]
