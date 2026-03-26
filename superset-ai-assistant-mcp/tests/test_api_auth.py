"""
Tests for the FastAPI auth endpoints.

Uses TestClient which provides a synchronous, cookie-aware HTTP client
backed by the real FastAPI app.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def _make_client(db_path: str) -> TestClient:
    """Create a fresh TestClient with a dedicated auth DB."""
    env = {
        "AUTH_DB_PATH": db_path,
        "AUTH_JWT_SECRET": "test-api-secret",
        "AUTH_JWT_TTL_HOURS": "1",
        "AUTH_PASSWORD_MIN_LENGTH": "8",
    }
    with patch.dict(os.environ, env, clear=False):
        # Reset singletons so each test gets its own AuthService instance
        import api.deps as deps_mod
        deps_mod._auth_service_instance = None
        deps_mod._AuthService = None

        from api.main import app
        return TestClient(app)


class TestAuthAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "api_test_auth.db")
        self.env_patch = patch.dict(
            os.environ,
            {
                "AUTH_DB_PATH": db_path,
                "AUTH_JWT_SECRET": "test-api-secret",
                "AUTH_JWT_TTL_HOURS": "1",
                "AUTH_PASSWORD_MIN_LENGTH": "8",
            },
            clear=False,
        )
        self.env_patch.start()
        # Reset singletons
        import api.deps as deps_mod
        deps_mod._auth_service_instance = None
        deps_mod._AuthService = None

        from api.main import app
        self.client = TestClient(app)

    def tearDown(self):
        import api.deps as deps_mod
        deps_mod._auth_service_instance = None
        deps_mod._AuthService = None
        self.env_patch.stop()
        self.temp_dir.cleanup()

    # -----------------------------------------------------------------------
    # POST /api/auth/register
    # -----------------------------------------------------------------------
    def test_register_success(self):
        resp = self.client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "strongpass"},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["username"], "alice")
        self.assertEqual(data["role"], "analyst")
        self.assertTrue(data["session_id"])

        # Cookie must be set
        cookie = resp.cookies.get("ai_assistant_auth_token")
        self.assertIsNotNone(cookie)
        self.assertTrue(len(cookie) > 10)

    def test_register_duplicate_returns_409(self):
        self.client.post(
            "/api/auth/register",
            json={"username": "bob", "password": "strongpass"},
        )
        resp = self.client.post(
            "/api/auth/register",
            json={"username": "bob", "password": "otherpass1"},
        )
        self.assertEqual(resp.status_code, 409)

    def test_register_short_password_returns_error(self):
        resp = self.client.post(
            "/api/auth/register",
            json={"username": "carol", "password": "short"},
        )
        # AuthService raises ValueError for short password -> 409
        self.assertIn(resp.status_code, [409, 422])

    def test_register_missing_fields_returns_422(self):
        resp = self.client.post("/api/auth/register", json={"username": "dave"})
        self.assertEqual(resp.status_code, 422)

    # -----------------------------------------------------------------------
    # POST /api/auth/login
    # -----------------------------------------------------------------------
    def test_login_success(self):
        self.client.post(
            "/api/auth/register",
            json={"username": "eve", "password": "strongpass"},
        )
        resp = self.client.post(
            "/api/auth/login",
            json={"username": "eve", "password": "strongpass"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], "eve")
        self.assertEqual(data["role"], "analyst")
        self.assertTrue(data["session_id"])

        cookie = resp.cookies.get("ai_assistant_auth_token")
        self.assertIsNotNone(cookie)

    def test_login_wrong_password_returns_401(self):
        self.client.post(
            "/api/auth/register",
            json={"username": "frank", "password": "strongpass"},
        )
        resp = self.client.post(
            "/api/auth/login",
            json={"username": "frank", "password": "wrongpass1"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_login_nonexistent_user_returns_401(self):
        resp = self.client.post(
            "/api/auth/login",
            json={"username": "ghost", "password": "strongpass"},
        )
        self.assertEqual(resp.status_code, 401)

    # -----------------------------------------------------------------------
    # GET /api/auth/me
    # -----------------------------------------------------------------------
    def test_me_with_valid_cookie(self):
        # Register and login to get the cookie
        self.client.post(
            "/api/auth/register",
            json={"username": "grace", "password": "strongpass"},
        )
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": "grace", "password": "strongpass"},
        )
        token = login_resp.cookies.get("ai_assistant_auth_token")

        # Use the cookie to call /me
        resp = self.client.get(
            "/api/auth/me",
            cookies={"ai_assistant_auth_token": token},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], "grace")
        self.assertEqual(data["role"], "analyst")

    def test_me_without_cookie_returns_401(self):
        resp = self.client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_me_with_invalid_cookie_returns_401(self):
        resp = self.client.get(
            "/api/auth/me",
            cookies={"ai_assistant_auth_token": "garbage-token"},
        )
        self.assertEqual(resp.status_code, 401)

    # -----------------------------------------------------------------------
    # POST /api/auth/logout
    # -----------------------------------------------------------------------
    def test_logout_clears_cookie(self):
        # Register + login
        self.client.post(
            "/api/auth/register",
            json={"username": "hank", "password": "strongpass"},
        )
        login_resp = self.client.post(
            "/api/auth/login",
            json={"username": "hank", "password": "strongpass"},
        )
        token = login_resp.cookies.get("ai_assistant_auth_token")
        self.assertIsNotNone(token)

        # Logout
        logout_resp = self.client.post("/api/auth/logout")
        self.assertEqual(logout_resp.status_code, 200)
        self.assertEqual(logout_resp.json()["message"], "Logged out.")

        # The cookie should be expired/deleted — TestClient may still send
        # the old value, but the server should have sent a Set-Cookie with
        # max-age=0.
        set_cookie_header = logout_resp.headers.get("set-cookie", "")
        self.assertIn("ai_assistant_auth_token", set_cookie_header)

    # -----------------------------------------------------------------------
    # GET /api/health
    # -----------------------------------------------------------------------
    def test_health_ok(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["auth_db_ok"])

    # -----------------------------------------------------------------------
    # Full flow: register -> /me -> logout -> /me fails
    # -----------------------------------------------------------------------
    def test_full_auth_flow(self):
        # 1. Register
        reg_resp = self.client.post(
            "/api/auth/register",
            json={"username": "ivan", "password": "strongpass"},
        )
        self.assertEqual(reg_resp.status_code, 201)
        token = reg_resp.cookies.get("ai_assistant_auth_token")

        # 2. /me works
        me_resp = self.client.get(
            "/api/auth/me",
            cookies={"ai_assistant_auth_token": token},
        )
        self.assertEqual(me_resp.status_code, 200)
        self.assertEqual(me_resp.json()["username"], "ivan")

        # 3. Logout
        self.client.post("/api/auth/logout")

        # 4. /me without cookie fails
        me_resp2 = self.client.get("/api/auth/me")
        self.assertEqual(me_resp2.status_code, 401)


if __name__ == "__main__":
    unittest.main()
