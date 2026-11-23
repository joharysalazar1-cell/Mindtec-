"""Tests for API input validation with wholly synthetic responses."""
import json
import os
import unittest
from unittest.mock import patch

from api_questionnaires import fetch_normalized_export


class FakeResponse:
    def __init__(self, payload):
        self.data = json.dumps(payload).encode("utf-8")
    def read(self, limit):
        return self.data[:limit]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
    def open(self, request, timeout):
        return FakeResponse(self.payload)


class ApiTests(unittest.TestCase):
    def test_requires_key(self):
        with patch.dict(os.environ, {"MINDTEC_QUESTIONNAIRES_API_URL":"https://example.invalid/export", "MINDTEC_QUESTIONNAIRES_API_KEY":""}):
            with self.assertRaisesRegex(ValueError, "API_KEY"):
                fetch_normalized_export()

    def test_requires_https(self):
        with patch.dict(os.environ, {"MINDTEC_QUESTIONNAIRES_API_URL":"http://example.invalid/export", "MINDTEC_QUESTIONNAIRES_API_KEY":"dummy"}):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                fetch_normalized_export()

    def test_reads_normalized_export(self):
        payload = {"envios":[{"envioKobo":"A","fechaVisita":"2026-11-15","codigoTienda":"T1","respuestas":[]}]}
        with patch.dict(os.environ, {"MINDTEC_QUESTIONNAIRES_API_URL":"https://example.invalid/export", "MINDTEC_QUESTIONNAIRES_API_KEY":"dummy"}):
            with patch("api_questionnaires.build_opener",return_value=FakeOpener(payload)):
                self.assertEqual(fetch_normalized_export(),payload)

    def test_rejects_pagination(self):
        payload = {"envios":[], "has_more":True}
        with patch.dict(os.environ, {"MINDTEC_QUESTIONNAIRES_API_URL":"https://example.invalid/export", "MINDTEC_QUESTIONNAIRES_API_KEY":"dummy"}):
            with patch("api_questionnaires.build_opener",return_value=FakeOpener(payload)):
                with self.assertRaisesRegex(ValueError, "paginado"):
                    fetch_normalized_export()

    def test_rejects_raw_kobo_list(self):
        with patch.dict(os.environ, {"MINDTEC_QUESTIONNAIRES_API_URL":"https://example.invalid/export", "MINDTEC_QUESTIONNAIRES_API_KEY":"dummy"}):
            with patch("api_questionnaires.build_opener",return_value=FakeOpener([{"_id":123}])):
                with self.assertRaisesRegex(ValueError, "envios"):
                    fetch_normalized_export()


if __name__ == "__main__":
    unittest.main()
