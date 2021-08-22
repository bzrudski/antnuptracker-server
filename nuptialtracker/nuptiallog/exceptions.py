from rest_framework import exceptions

class BadLocationUrlException(exceptions.APIException):
    status_code = 400
    default_detail = {"detail": "Provide a location to use for sorting."}
    default_code = "no_coordinates_location"
