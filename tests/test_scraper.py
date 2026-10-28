import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from ubuntu_l10n import scraper


class JsonStorageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.config_file = root / "config" / "config.json"
        self.cache_file = root / "cache" / "cache.json"

    def test_save_config_is_atomic_and_private(self):
        with patch.object(scraper, "CONFIG_FILE", self.config_file):
            scraper.save_config({"language": "sv"})
            self.assertEqual(scraper.load_config(), {"language": "sv"})
        self.assertEqual(stat.S_IMODE(self.config_file.stat().st_mode), 0o600)
        self.assertEqual(list(self.config_file.parent.iterdir()), [self.config_file])

    def test_cache_round_trip_and_corrupt_cache_recovery(self):
        with patch.object(scraper, "CACHE_FILE", self.cache_file):
            scraper.save_cache("noble", "sv", [{"name": "example"}])
            data, timestamp = scraper.load_cache("noble", "sv")
            self.assertEqual(data, [{"name": "example"}])
            self.assertIsInstance(timestamp, float)

            self.cache_file.write_text("not json", encoding="utf-8")
            self.assertEqual(scraper.load_cache("noble", "sv"), (None, None))
            self.cache_file.write_text('{"noble_sv": {"timestamp": "bad"}}', encoding="utf-8")
            self.assertEqual(scraper.load_cache("noble", "sv"), (None, None))
            scraper.save_cache("noble", "sv", [])
            self.assertEqual(json.loads(self.cache_file.read_text(encoding="utf-8"))["noble_sv"]["data"], [])


class RequestRetryTests(unittest.TestCase):
    def test_retries_rate_limit_and_honours_retry_after(self):
        rate_limited = Mock(status_code=429, headers={"Retry-After": "3"})
        success = Mock(status_code=200, headers={})
        success.raise_for_status.return_value = None
        session = Mock()
        session.get.side_effect = [rate_limited, success]
        with patch.object(scraper.time, "sleep") as sleep:
            result = scraper._request_with_retry(session, "https://example.invalid", max_retries=2)
        self.assertIs(result, success)
        sleep.assert_called_once_with(3.0)
        self.assertEqual(session.get.call_count, 2)

    def test_retries_transient_server_error(self):
        unavailable = Mock(status_code=503, headers={})
        success = Mock(status_code=200, headers={})
        success.raise_for_status.return_value = None
        session = Mock()
        session.get.side_effect = [unavailable, success]
        with patch.object(scraper.time, "sleep") as sleep:
            self.assertIs(scraper._request_with_retry(session, "https://example.invalid", max_retries=2), success)
        sleep.assert_called_once_with(2)

    def test_retries_timeout_but_propagates_final_timeout(self):
        success = Mock(status_code=200, headers={})
        success.raise_for_status.return_value = None
        session = Mock()
        session.get.side_effect = [requests.Timeout(), success]
        with patch.object(scraper.time, "sleep"):
            self.assertIs(scraper._request_with_retry(session, "https://example.invalid", max_retries=2), success)

        session.get.side_effect = requests.Timeout()
        with patch.object(scraper.time, "sleep"):
            with self.assertRaises(requests.Timeout):
                scraper._request_with_retry(session, "https://example.invalid", max_retries=1)

    def test_does_not_retry_client_errors(self):
        response = Mock(status_code=404, headers={})
        response.raise_for_status.side_effect = requests.HTTPError("not found")
        session = Mock()
        session.get.return_value = response
        with self.assertRaises(requests.HTTPError):
            scraper._request_with_retry(session, "https://example.invalid", max_retries=3)
        session.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
