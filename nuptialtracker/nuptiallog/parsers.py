#
# parsers.py
# AntNupTracker Server, backend for recording and managing ant nuptial flight data
# Copyright (C) 2020-2021 Abouheif Lab
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

from rest_framework.parsers import FileUploadParser

class ImageUploadParser(FileUploadParser):
    """
    Image upload parser. Simple modification of the
    FileUploadParser with the modification of only
    accepting image files.
    """
    media_type = "image/*"
