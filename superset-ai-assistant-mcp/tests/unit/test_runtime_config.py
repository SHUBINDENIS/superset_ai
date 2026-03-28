import unittest

from api.runtime_config import RuntimeConfigError, collect_runtime_config_report, validate_runtime_config


class TestRuntimeConfig(unittest.TestCase):
    def test_development_mode_warns_but_does_not_fail_for_weak_jwt_secret(self):
        report = validate_runtime_config(
            {
                "ASSISTANT_DEPLOYMENT_MODE": "development",
                "OPENAI_API_KEY": "sk-test-1234567890",
                "OPENAI_MODEL": "gpt-5.4-mini",
                "SUPERSET_PUBLIC_URL": "http://127.0.0.1:8088",
                "AUTH_JWT_SECRET": "change_me_please",
            }
        )
        self.assertEqual(report["mode"], "development")
        self.assertTrue(any("AUTH_JWT_SECRET is weak" in item for item in report["warnings"]))

    def test_production_mode_rejects_weak_jwt_secret(self):
        with self.assertRaisesRegex(RuntimeConfigError, "AUTH_JWT_SECRET must be non-placeholder"):
            validate_runtime_config(
                {
                    "ASSISTANT_DEPLOYMENT_MODE": "production",
                    "OPENAI_API_KEY": "sk-test-1234567890",
                    "OPENAI_MODEL": "gpt-5.4-mini",
                    "SUPERSET_PUBLIC_URL": "https://superset.example.com",
                    "AUTH_JWT_SECRET": "change_me_please",
                }
            )

    def test_production_mode_rejects_local_public_url(self):
        with self.assertRaisesRegex(RuntimeConfigError, "SUPERSET_PUBLIC_URL must not point to localhost"):
            validate_runtime_config(
                {
                    "ASSISTANT_DEPLOYMENT_MODE": "production",
                    "OPENAI_API_KEY": "sk-test-1234567890",
                    "OPENAI_MODEL": "gpt-5.4-mini",
                    "SUPERSET_PUBLIC_URL": "http://127.0.0.1:8088",
                    "AUTH_JWT_SECRET": "x" * 32,
                }
            )

    def test_production_mode_rejects_mismatched_share_origin(self):
        with self.assertRaisesRegex(RuntimeConfigError, "US15_SHARE_BASE_URL must match SUPERSET_PUBLIC_URL origin"):
            validate_runtime_config(
                {
                    "ASSISTANT_DEPLOYMENT_MODE": "production",
                    "OPENAI_API_KEY": "sk-test-1234567890",
                    "OPENAI_MODEL": "gpt-5.4-mini",
                    "SUPERSET_PUBLIC_URL": "https://superset.example.com",
                    "US15_SHARE_BASE_URL": "https://share.example.com",
                    "AUTH_JWT_SECRET": "x" * 32,
                }
            )

    def test_production_mode_rejects_localhost_cors_origin(self):
        with self.assertRaisesRegex(RuntimeConfigError, "API_CORS_ORIGINS must not include localhost"):
            validate_runtime_config(
                {
                    "ASSISTANT_DEPLOYMENT_MODE": "production",
                    "OPENAI_API_KEY": "sk-test-1234567890",
                    "OPENAI_MODEL": "gpt-5.4-mini",
                    "SUPERSET_PUBLIC_URL": "https://superset.example.com",
                    "AUTH_JWT_SECRET": "x" * 32,
                    "API_CORS_ORIGINS": "http://localhost:3001",
                }
            )

    def test_production_mode_without_cors_override_assumes_same_origin_proxy(self):
        report = collect_runtime_config_report(
            {
                "ASSISTANT_DEPLOYMENT_MODE": "production",
                "OPENAI_API_KEY": "sk-test-1234567890",
                "OPENAI_MODEL": "gpt-5.4-mini",
                "SUPERSET_PUBLIC_URL": "https://superset.example.com",
                "AUTH_JWT_SECRET": "x" * 32,
            }
        )
        self.assertEqual(report["errors"], [])
        self.assertIn(
            "API_CORS_ORIGINS not set; same-origin proxy deployment assumed",
            report["checks"],
        )
