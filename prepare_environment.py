#
# prepare_environment.py
# Copyright (C) 2023- Abouheif Lab
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

"""
Environment preparation

This script prepares a file with some of the environment variables required for development.

"""

import argparse
import random
import os
import string
from typing import Optional

def generate_secret_key(length: int) -> str:
    """
    Generate a Django secret key with a certain length.

    :param length: length of the secret key.
    :returns: string containing the secret key.
    """
    possible_characters = string.ascii_letters + string.digits
    return "".join(random.choices(population=possible_characters, k=length))


def generate_environment_file(secret_key_length: int, taxonomy_file: str, username: Optional[str], password: Optional[str]):
    """
    Generate an environment variables file containing the secret key.

    This function writes to envfile.env. If the file exists already, it will be overwritten.

    :param secret_key_length: length of the secret key to generate.
    :param taxonomy_file: absolute path to the taxonomy file.
    :param username: database username if using PostgreSQL (optional).
    :param password: database password if using PostgreSQL (optional).
    """
    with open("envfile.env", 'w', encoding='utf-8') as envfile:
        secret_key=generate_secret_key(length=secret_key_length)
        envfile.write(f"export SECRET_KEY=\"{secret_key}\"\n")
        envfile.write(f"export TAXONOMY_FILE=\"{taxonomy_file}\"\n")

        if username is not None and password is not None:
            envfile.write(f"export ANT_USERNAME=\"{username}\"\n")
            envfile.write(f"export ANT_PASSWORD=\"{password}\"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Environment preparation script for AntNupTracker."
                                     "\n\nThis script generates an environment file that will hold all the environment variables that"
                                     "you need to get an AntNupTracker test server running.")
    parser.add_argument('-u', '--username', help="Database username.")
    parser.add_argument('-p', '--password', help='Database password.')
    parser.add_argument('-l', '--secret-key-length', type=int, default=32, help='Length of Django secret key (default: 32)')
    parser.add_argument('-t', '--taxonomy-file', help='Taxonomy file path. Path to the raw taxonomy file (if custom taxonomy used).')

    args = parser.parse_args()

    username = args.username
    password = args.password
    secret_key_length = args.secret_key_length
    taxonomy_file = os.path.abspath(args.taxonomy_file if args.taxonomy_file is not None else "./nuptialtracker/nuptiallog/taxonomyRaw")
    generate_environment_file(secret_key_length=secret_key_length, taxonomy_file=taxonomy_file, username=username, password=password)