#
#  authToken.py
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

import time
import json
import cryptography
import jwt
import os

def getToken():
    try:
        filename = os.getenv("TOKFILE")
        # print("Token file: "+ filename)
        tokenFile = open(filename, "rt")
        token = tokenFile.readline().strip()
        iatString = tokenFile.readline()

        iat = float(iatString)
        currentTime = time.time()

        if (currentTime-iat >= 3600):
            newTokenDict = generateToken()
            return newTokenDict["token"]
        return token
    except FileNotFoundError:
        newTokenDict = generateToken()
        return newTokenDict["token"]

def generateToken():
    alg = "ES256"
    kid = os.getenv("KID")
    iss = os.getenv("ISS")
    iat = time.time()

    filename = os.getenv("KEYPATH")
    keyFile = open(filename, "rt")
    key = keyFile.read()
    keyFile.close()

    headers = {
        "alg"   :   alg,
        "kid"   :   kid,
    }

    body = {
        "iss"   : iss,
        "iat"   : iat,
    }

    token = jwt.encode(body, key, algorithm='ES256', headers=headers)
    tokenString = token.decode('ascii')

    tokenPath = os.getenv("TOKFILE")
    # print("Token file: "+ tokenPath)
    tokenFile = open(tokenPath, "wt")
    tokenFile.write(tokenString)
    tokenFile.write("\n")
    tokenFile.write(str(iat))
    tokenFile.close()

    return {'token':tokenString, 'iat': iat}