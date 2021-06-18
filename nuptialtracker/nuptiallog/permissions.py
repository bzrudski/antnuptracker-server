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
from .models import Role
from django.contrib.auth.models import AnonymousUser

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Defines permission (for comments) to only allow the owner
    of an object (comment) to modify and remove it.
    """
    def has_object_permission(self, request, view, obj):
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
            else:
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
        if request.auth == None:
            return False

        return request.user.flightuser.professional


class IsProfessionalOrReadOnly(permissions.BasePermission):
    """
    For privileges granted only to professional myrmecologists.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.user is AnonymousUser:
            return False

        return request.user.flightuser.professional

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.auth == None:
            return False

        return request.user.flightuser.professional