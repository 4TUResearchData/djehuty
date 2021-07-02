from dataclasses import dataclass
from urllib.request import urlretrieve
import http.client
import json


# ENDPOINT
# -----------------------------------------------------------------------------
# This class wraps the connection details to interact with a
# Figshare-compatible endpoint.

@dataclass
class FigshareEndpoint:
    api_location: str = "/v2"
    domain:       str = "api.figshare.com"
    token:        str = None


# UTILITY PROCEDURES
# -----------------------------------------------------------------------------

def request (endpoint: FigshareEndpoint,
             action: str,
             path: str,
             parameters):
    """
    Procedure to perform a request to a Figshare-compatible endpoint.

    :param str endpoint:   An instance of FigshareEndpoint.
    :param str action:     Either GET or POST.
    :param str path:       The absolute API path after the base location.
    :param str parameters: A dictionary of parameters to send in the request.
    """

    connection = http.client.HTTPSConnection(endpoint.domain)
    headers    = {
        "Accept": "application/json",
        "Authorization": "token " + token
    }

    connection.request(action, endpoint.api_location + path, None, headers)
    response   = connection.getresponse()

    if 200 > response.status > 299:
        connection.close()
        sys.stderr.write("{domain} returned {status}".format(
            domain = endpoint.domain,
            status = response.status))
        return None
    else:
        jsonData = respond.read()
        connection.close()
        data = json.loads(jsonData.decode())
        return data

def get (endpoint: FigshareEndpoint, path: str, parameters):
    """Procedure to perform a GET request to a Figshare-compatible endpoint."""
    return figshare_request (endpoint, "GET", path, parameters)

def post (endpoint: FigshareEndpoint, path: str, parameters):
    """Procedure to perform a POST request to a Figshare-compatible endpoint."""
    return figshare_request (endpoint, "POST", path, parameters)
