#
#  notifications.py
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

from firebase_admin import messaging
from .models import Device
from .firebase import default_app as FirebaseApp

def send_notifications(devices, title, body):

    tokens = [token for token in devices]

    # print(tokens)

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body)
    )

    response = messaging.send_multicast(message)

    print("{} devices: {} success + {} failure".format(
        len(devices),
        response.success_count,
        response.failure_count
        ))

    print("Failures: ")

    for send_response in response.responses:
        if not send_response.success:
            print(send_response.exception)

# # Payload Generation
# class IllegalDeviceException(Exception):
#     pass

# def generatePayload(deviceType, body, title, flightID=None):
#     """
#     Create the notification payload.

#     Parameters:
#         - deviceType: String representing the type of device.
#                       Acceptable values are "IOS", "ANDROID".
#                       If none of above, IllegalDeviceException is raised.

#         - body:       Notification body.
        
#         - title:      Notification title.

#     Returns:
#         - JSON representation of the notification payload.

#     Raises:
#         - IllegalDeviceException if the deviceType is not a permitted
#           value.
#     """
#     if (deviceType == "IOS"):
#         return generateIosPayload(body, title, flightID=flightID)
#     elif (deviceType == "ANDROID"):
#         return generateAndroidPayload(body, title, flightID=flightID)
#     else:
#         raise IllegalDeviceException("Device type is not a legal option")

# def generateIosPayload(body, title, flightID=None):
#     payload = {
#         "aps"   :   {
#             "category" :    "FLIGHT_CHANGE",
#             "alert"    :    {
#                 "title" :   title,
#                 "body"  :   body,
#             },
#             "sound"    : "default",
#         },
#     }

#     if flightID:
#         payload["FLIGHT_ID"] = flightID

#     topic = os.getenv("APNS_TOPIC")

#     return (topic, json.dumps(payload))

# def generateAndroidPayload(body, title, flightID=None):
#     pass

# def generateHeader(topic, token):
#     return {"apns-topic":topic, "Authorization": "Bearer " + token, "Content-Type" : "application/json"}

# # Notification token generation
# def generateNotificationToken():
#     return getToken()

# # Notification sending
# def sendNotification(topic, content, deviceToken, authToken, development=True):
#     if (development):
#         url = "https://api.sandbox.push.apple.com:443/3/device/" + deviceToken
#     else:
#         url = "https://api.push.apple.com:443/3/device/" + deviceToken
#     headers = generateHeader(topic, authToken)
#     headerArr = []

#     for header in headers.keys():
#         headerString = f"{header}:{headers[header]}"
#         headerArr.append(headerString)

#     # curl.setopt(pycurl.POSTFIELDS, content)
#     # curl.setopt(pycurl.HTTPHEADER, headerArr)
#     # curl.setopt(pycurl.URL, url)

#     # curl.perform()

#     curlexec = os.getenv("CURLPATH") + "/curl"
#     args = [curlexec, "--http2"]
#     for header in headerArr:
#         args.extend(["-H", header])
#     # args.extend(headerArr)
#     args.extend(["-d", content])
#     args.append(url)
#     args.extend(["-w", "\n%{response_code}"])

#     # print(args)

#     p = run(args, stdout=PIPE, stderr=PIPE)

#     # print(p.stdout)

#     return int(p.stdout.split(b'\n')[-1])

#     # return curl.getinfo(pycurl.HTTP_CODE)

# def sendAllNotifications(title, body, devices, development=True, flightID=None):
#     # devices = Device.objects.all().filter(active=True)
#     totalDevices = 0
#     totalSent = 0
#     successes = 0
#     failures = 0

#     # c = pycurl.Curl()
#     # c.setopt(pycurl.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_2_0)

#     authToken = getToken()

#     topic, content = generatePayload("IOS", body, title, flightID=flightID)

#     for device in devices:
#         totalDevices += 1
#         if (device.deviceToken != "None"):
#             # topic, content = generatePayload(device.platform, body, title)
#             totalSent += 1
#             response_code = sendNotification(topic, content, device.deviceToken, authToken, development=development)

#             if (response_code == 200):
#                 successes += 1
#             else:
#                 failures += 1

#     # c.close()

#     resultDict = {
#             "totalDevices":totalDevices,
#             "totalSent":totalSent,
#             "successes":successes,
#             "failures":failures,
#             }

#     print(resultDict)
#     return resultDict
