import unittest
import hmac
from django.conf import settings

from modelservice.auth import validate_external_auth
from modelservice.conf import EXTERNAL_AUTH_SHARED_SECRET


class TestScopeManager(unittest.TestCase):
    def test_external_auth_empty(self):
        assert validate_external_auth("bob@example.com", "") is False

    def test_external_auth_invalid(self):
        assert validate_external_auth("bob@example.com", "::simpl-exterrnal-auth::") is False
        assert validate_external_auth("bob@example.com", "::simpl-exterrnal-auth::blah-blah-blah") is False

    def test_external_auth_valid(self):
        h = hmac.new(
            key=EXTERNAL_AUTH_SHARED_SECRET.encode("utf-8"),
            msg="bob@example.com".encode("utf-8"),
            digestmod="sha256"
        )

        msg = f"::simpl-external-auth::{h.hexdigest()}"

        assert validate_external_auth("bob@example.com", msg) is True
