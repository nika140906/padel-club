"""The ladder's one call to the bookings service.

When a member joins the ladder, the ladder asks bookings who they are with
GET /auth/me, sending the member's own login token along. Bookings owns the
member accounts, so it is the only place that knows the username.

It uses urllib from Python's standard library, so no extra package is needed.
"""
import json
import urllib.error
import urllib.request


class BookingsUnavailable(Exception):
    """Bookings did not answer in time, could not be reached, or answered with an error."""


def get_member(bookings_url, authorization, timeout_s):
    """Return the logged-in member as {"id", "username"}, or None if the account is gone.

    authorization is the member's "Bearer <token>" header, passed on unchanged.
    timeout_s stops the call from hanging: if bookings has not connected or
    sent data for that many seconds, the call gives up.
    """
    request = urllib.request.Request(
        bookings_url.rstrip("/") + "/auth/me",
        headers={"Authorization": authorization, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:  # bookings answered, but not with 200
        error.close()
        if error.code == 404:
            return None
        raise BookingsUnavailable(f"bookings answered {error.code}") from error
    except (OSError, ValueError) as error:  # refused, timed out, DNS failed, or not JSON
        raise BookingsUnavailable(str(error)) from error
