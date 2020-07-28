#
#  admin.py
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

from django.contrib import admin
from .models import Flight, Comment, Device, Changelog, FlightUser
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.core.mail import EmailMessage

from knox.models import AuthToken
from knox.admin import AuthTokenAdmin as BaseAuthTokenAdmin

# Register your models here.
class CommentInline(admin.StackedInline):
    model = Comment
    can_delete = True
    extra = 0

class FlightLogAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Classification",      {'fields': ['genus', 'species']}),
        ("Flight information",  {'fields': ['latitude','longitude','dateOfFlight']}),
        ("Contact",             {'fields': ['owner']}),
    ]
    
    inlines = (CommentInline, )
    list_display=('flightID','genus','species','latitude','longitude','dateOfFlight')
    list_filter = ['genus','species','latitude','longitude', 'dateOfFlight']
    search_fields = ['latitude','longitude']
    #ordering = ['genus','species','location']
    ordering = ['flightID']

admin.site.register(Flight, FlightLogAdmin)

class FlightUserInline(admin.TabularInline):
    model = FlightUser
    exclude = ['genera', 'species']

class FlightDeviceInline(admin.StackedInline):
    model = Device
    can_delete = False
    extra = 0
    fields = ['deviceID', 'model', 'platform', 'lastLoggedIn', 'authToken', 'active']
    readonly_fields = ['deviceID', 'model', 'platform', 'lastLoggedIn', 'authToken']

class UserAdmin(BaseUserAdmin):
    def get_role(self, obj):
        status = obj.flightuser.status()

        if status == 0:
            return "Citizen Scientist"
        elif status == 1:
            return "Professional Myrmecologist"
        else:
            return "Flagged"

    get_role.short_description = 'role'
    list_display = ('username', 'email', 'is_active', 'get_role')
    inlines = [FlightUserInline, FlightDeviceInline]

    def flag_user(self, request, queryset):
        for user in queryset:
            user.flightuser.flag()

    def unflag_user(self, request, queryset):
        for user in queryset:
            user.flightuser.unflag()

    def email_professional_user(self, request, queryset):
        for user in queryset:
            if not user.flightuser.is_professional:
                continue

            to_addr = user.email
            subject = "AntNupTracker Account Information"
            message = render_to_string('nuptiallog/ProfessionalCheckEmail.html', {
                'user'  : user.username,
                'institution'   : user.flightuser.institution
            })

            email = EmailMessage(subject, message, to=[to_addr])
            email.content_subtype = 'html'

            try:
                email.send()
            except:
                print("Error sending account email")

    actions = [flag_user, unflag_user, email_professional_user]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

class FlightDeviceAdmin(admin.ModelAdmin):
    model = Device

    fields = ['deviceID', 'user', 'platform', 'model', 'lastLoggedIn', 'authToken']

    #inlines = [EventLogInline]
    list_display = ['deviceID', 'model', 'platform', 'user']

    def log_device_out(self, request, queryset):
        for device in queryset:
            device.logout()

    actions = [log_device_out]

admin.site.register(Device, FlightDeviceAdmin)

class AuthTokenAdmin(BaseAuthTokenAdmin):
    inlines = [FlightDeviceInline]

admin.site.unregister(AuthToken)
admin.site.register(AuthToken, AuthTokenAdmin)