import base64
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


logger = logging.getLogger(__name__)


class PayPalError(Exception):
    pass


def _paypal_base_url():
    if settings.PAYPAL_MODE == "live":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


def _paypal_access_token():
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
        raise PayPalError("PayPal sandbox credentials are not configured.")

    credentials = f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    request = Request(
        f"{_paypal_base_url()}/v1/oauth2/token",
        data=urlencode({"grant_type": "client_credentials"}).encode("ascii"),
        headers={
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.warning("PayPal access-token request failed: %s", error)
        raise PayPalError("PayPal could not authorize this payment. Please try again.") from error

    access_token = data.get("access_token")
    if not access_token:
        raise PayPalError("PayPal did not return an access token.")
    return access_token


def paypal_request(method, path, payload=None, request_id=None):
    access_token = _paypal_access_token()
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if request_id:
        headers["PayPal-Request-Id"] = request_id

    request = Request(
        f"{_paypal_base_url()}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        logger.warning("PayPal API returned HTTP %s: %s", error.code, error_body)
        raise PayPalError("PayPal could not complete the payment request.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        logger.warning("PayPal API request failed: %s", error)
        raise PayPalError("PayPal is temporarily unavailable. Please try again.") from error
