from __future__ import annotations

import unittest

from scripts.phase9_production_readiness import expected_callback, validate_public_base_url


class Phase9ReadinessContracts(unittest.TestCase):
    def test_https_url_is_valid(self):
        valid, _ = validate_public_base_url("https://mdrrmo.example.gov.ph")
        self.assertTrue(valid)

    def test_http_url_is_rejected(self):
        valid, _ = validate_public_base_url("http://mdrrmo.example.gov.ph")
        self.assertFalse(valid)

    def test_localhost_is_rejected(self):
        valid, _ = validate_public_base_url("https://localhost:8501")
        self.assertFalse(valid)

    def test_oidc_callback_contract(self):
        self.assertEqual(
            expected_callback("https://mdrrmo.example.gov.ph/"),
            "https://mdrrmo.example.gov.ph/oauth2callback",
        )


if __name__ == "__main__":
    unittest.main()
