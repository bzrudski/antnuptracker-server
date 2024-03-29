#
#  pandasViews.py
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

from rest_pandas import PandasView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import BasicAuthentication
from rest_framework.generics import GenericAPIView
from .models import Flight
from .serializers import FlightSerializerExport
from django.utils import timezone

class FlightDataExport(PandasView):
    queryset = Flight.objects.all()
    serializer_class = FlightSerializerExport
    permission_classes = [IsAuthenticated]
    authentication_classes = [BasicAuthentication]

    def get_pandas_filename(self, request, format):
        date = timezone.now()
        date_string = date.strftime("%d_%b_%Y_%H%M%S")
        return f"FlightData_{date_string}"