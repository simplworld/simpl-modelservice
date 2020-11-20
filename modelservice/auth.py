import re
import hmac

from .conf import EXTERNAL_AUTH_SHARED_SECRET


EXTERNAL_RE = re.compile(r'^::simpl-external-auth::(.*)$')


def validate_external_auth(email, value):
    """
    In order to authenticate users via third party systems such as LTI, OAuth2,
    etc. we are providing this way for the frontend or UI to authenticate a
    Simpl user and passing an HMAC message which can be trusted by the modelservice.

    Using this method requires the shared secret in `EXTERNAL_AUTH_SHARED_SECRET`
    be kept secret and only shared between the UI doing the authentication and
    the modelservice.

    External services should provide the HMAC using the following scheme as the
    "password" during authentication:

    ::simpl-external-auth::<hmac>

    For example, if we're authenticating `bob@example.com` with a secret key of
    "password1234" it should present this string:

    ::simpl-external-auth::eeabc7093594a00ea1abe8d9efa3347128eb995010871e008f9ffefad6b2a654

    """
    m = EXTERNAL_RE.match(value)

    # We didn't match the structure
    if m is None:
        return False

    this_hash = m.group(1)

    # Build the hash
    h = hmac.new(
        key=EXTERNAL_AUTH_SHARED_SECRET.encode("utf-8"),
        msg=email.encode("utf-8"),
        digestmod="sha256",
    )

    # If our hashes match, authenticate them
    if this_hash == h.hexdigest():
        return True

    # Deny non-matches
    return False
