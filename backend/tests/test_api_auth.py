import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import config as config_module
from backend.app.db import init_db
from backend.app.main import app


class TestApiAuth(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        os.environ["APP_DB_PATH"] = str(Path(self.tmp_dir.name) / "api.db")
        os.environ["APP_ADMIN_USERNAME"] = "admin"
        os.environ["APP_ADMIN_PASSWORD"] = "secret"
        config_module.get_settings.cache_clear()
        init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        config_module.get_settings.cache_clear()
        os.environ.pop("APP_DB_PATH", None)
        os.environ.pop("APP_ADMIN_USERNAME", None)
        os.environ.pop("APP_ADMIN_PASSWORD", None)
        self.tmp_dir.cleanup()

    def test_login_and_protected_endpoint(self) -> None:
        r = self.client.post("/auth/login", json={"username": "admin", "password": "secret"})
        self.assertEqual(r.status_code, 200)

        p = self.client.get("/api/protected")
        self.assertEqual(p.status_code, 200)
        self.assertTrue(p.json().get("ok"))

    def test_protected_requires_auth(self) -> None:
        r = self.client.get("/api/protected")
        self.assertEqual(r.status_code, 401)

    def test_run_detail_endpoint(self) -> None:
        login = self.client.post("/auth/login", json={"username": "admin", "password": "secret"})
        self.assertEqual(login.status_code, 200)

        created = self.client.post("/api/runs", json={"run_type": "ingestion", "status": "running"})
        self.assertEqual(created.status_code, 200)
        run_id = created.json()["id"]

        detail = self.client.get(f"/api/runs/{run_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["item"]["id"], run_id)

    def test_source_policy_check_endpoint(self) -> None:
        login = self.client.post("/auth/login", json={"username": "admin", "password": "secret"})
        self.assertEqual(login.status_code, 200)

        created = self.client.post(
            "/api/sources",
            json={
                "name": "Policy Source",
                "risk_level": "yellow",
                "is_enabled": True,
            },
        )
        self.assertEqual(created.status_code, 200)
        source_id = created.json()["id"]

        check = self.client.get(f"/api/sources/{source_id}/policy-check")
        self.assertEqual(check.status_code, 200)
        body = check.json()
        self.assertFalse(body["allowed"])
        self.assertGreaterEqual(len(body["issues"]), 1)


if __name__ == "__main__":
    unittest.main()
