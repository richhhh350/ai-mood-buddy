from fastapi.testclient import TestClient
import unittest

from app.main import app


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())


if __name__ == "__main__":
    unittest.main(verbosity=2)
