#
#  permissions.py
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

from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from .models import Flight

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Defines permission (for comments) to only allow the owner
    of an object (comment) to modify and remove it.
    """
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.owner == request.user

class IsOwner(permissions.BasePermission):
    """
    Defines permission to only allow the owner of an object
    to view.
    """
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user

class IsOwnerOrProfessionalOrReadOnly(permissions.BasePermission):
    """
    Defines permission to only allow the owner of an object or
    a professional to edit.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        elif request.user is AnonymousUser:
            return False

        else:
            if obj.owner == request.user:
                return True
            
            return request.user.flightuser.professional

class IsProfessional(permissions.BasePermission):
    """
    For privileges granted only to professional myrmecologists.
    """

    def has_object_permission(self, request, view, obj):
        if request.user is AnonymousUser:
            return False

        return request.user.flightuser.professional

    def has_permission(self, request, view):
        if request.auth is None:
            return False

        return request.user.flightuser.professional


class IsProfessionalOrReadOnly(permissions.BasePermission):
    """
    For privileges granted only to professional myrmecologists.
    """

    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.flightuser.professional

    def has_permission(self, request, view):
        if isinstance(request.user, AnonymousUser):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if request.auth is None:
            return False

        return request.user.flightuser.professional

class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Defines permission (for comments) to only allow the owner
    of an object (comment) to modify and remove it.
    """
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.author == request.user

class IsAuthor(permissions.BasePermission):
    """
    Defines permission (for comments) to only allow the owner
    of an object (comment) to modify and remove it.
    """
    def has_object_permission(self, request, view, obj):
        return obj.author == request.user

class IsFlightOwnerOrReadOnly(permissions.BasePermission):
    """
    Defines permission for flight images to only allow the
    owner of a flight to add/modify images.
    """
    def __init__(self, flight_id) -> None:
        self.flight_id = flight_id
        super().__init__()

    def has_permission(self, request, view):
        if isinstance(request.user, AnonymousUser):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        # print("Checking flight permission...")
        has_permission = Flight.objects.get(pk=self.flight_id).owner == request.user
        # print("User has permission: " + str(has_permission))
        return has_permission

    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        # print("Checking flight permission...")
        has_permission = Flight.objects.get(pk=self.flight_id).owner == request.user
        # print("User has permission: " + str(has_permission))
        return has_permission


class IsImageOwnerOrReadOnly(permissions.BasePermission):
    """
    Defines permission (for flight images) to only allow the owner
    of an object (flight image) to modify and remove it.
    """
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        # print("Checking image permissions...")
        return obj.created_by == request.user

class IsUserOrAuthenticatedReadOnly(permissions.BasePermission):
    """
    Defines an object permission for user objects to ensure that a user can
    only modify their own details (and not those of others).
    """
    def has_object_permission(self, request, view, obj):
        print("Checking object permissions...")
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.user == obj.user:
            print("Request use is the user in question...")
            return True

        return False
