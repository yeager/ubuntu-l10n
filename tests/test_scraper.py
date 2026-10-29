import json
import stat
import tempfile
import threading
import time
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

    def test_cache_rejects_invalid_timestamps(self):
        invalid_timestamps = ("bad", True, float("nan"), float("inf"), -1)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with patch.object(scraper, "CACHE_FILE", self.cache_file):
            for timestamp in invalid_timestamps:
                with self.subTest(timestamp=timestamp):
                    self.cache_file.write_text(
                        json.dumps({"noble_sv": {"data": [], "timestamp": timestamp}}),
                        encoding="utf-8",
                    )
                    self.assertEqual(scraper.load_cache("noble", "sv"), (None, None))

    def test_concurrent_cache_updates_preserve_both_entries(self):
        first_write_started = threading.Event()
        release_first_write = threading.Event()
        second_writer_started = threading.Event()
        write_guard = threading.Lock()
        active_writes = 0
        concurrent_writes = False
        original_write = scraper._atomic_write_json

        def controlled_write(path, data):
            nonlocal active_writes, concurrent_writes
            with write_guard:
                if active_writes:
                    concurrent_writes = True
                active_writes += 1
                write_number = active_writes
            if write_number == 1:
                first_write_started.set()
                if not release_first_write.wait(timeout=5):
                    raise TimeoutError("test did not release the first cache write")
            try:
                original_write(path, data)
            finally:
                with write_guard:
                    active_writes -= 1

        with (
            patch.object(scraper, "CACHE_FILE", self.cache_file),
            patch.object(scraper, "CACHE_DIR", self.cache_file.parent),
            patch.object(scraper, "_atomic_write_json", side_effect=controlled_write),
        ):
            first = threading.Thread(
                target=scraper.save_cache, args=("noble", "sv", [{"name": "Swedish"}]),
            )
            second = threading.Thread(
                target=lambda: (
                    second_writer_started.set(),
                    scraper.save_cache("noble", "de", [{"name": "German"}]),
                ),
            )
            first.start()
            self.assertTrue(first_write_started.wait(timeout=2))
            second.start()
            self.assertTrue(second_writer_started.wait(timeout=2))
            time.sleep(0.05)
            release_first_write.set()
            first.join(timeout=5)
            second.join(timeout=5)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertFalse(concurrent_writes)
        cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
        self.assertEqual(cache["noble_sv"]["data"], [{"name": "Swedish"}])
        self.assertEqual(cache["noble_de"]["data"], [{"name": "German"}])


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


class LaunchpadPaginationTests(unittest.TestCase):
    def _cached_package(self):
        package = scraper.PackageStats(
            name="example", translated_pct=75.0, untranslated=25,
            need_review=0, changed=0, total=100, last_edited="",
            last_editor="", translate_url="https://translations.launchpad.net/example",
        )
        return package, scraper._packages_to_dicts([package])

    def test_future_cache_timestamp_is_shown_as_unknown_and_refreshed(self):
        package, cached_data = self._cached_package()
        session = Mock()
        session.headers = {}
        cache_callback = Mock()

        with (
            patch.object(scraper, "load_cache", return_value=(cached_data, 1200.0)),
            patch.object(scraper.time, "time", return_value=1000.0),
            patch.object(scraper.requests, "Session", return_value=session),
            patch.object(scraper, "_request_with_retry", side_effect=requests.ConnectionError("offline")),
        ):
            with self.assertRaises(requests.ConnectionError):
                scraper.fetch_all_packages("noble", "sv", cache_cb=cache_callback)

        cache_callback.assert_called_once_with([package], None)

    def test_malformed_cached_package_is_ignored_and_refetched(self):
        session = Mock()
        session.headers = {}
        response = Mock(text="<html></html>")
        cache_callback = Mock()

        with (
            patch.object(scraper, "load_cache", return_value=([{"name": "broken"}], 1000.0)),
            patch.object(scraper.time, "time", return_value=1000.0),
            patch.object(scraper.requests, "Session", return_value=session),
            patch.object(scraper, "_request_with_retry", return_value=response) as request,
            patch.object(scraper, "save_cache") as save_cache,
        ):
            result = scraper.fetch_all_packages("noble", "sv", cache_cb=cache_callback)

        self.assertEqual(result, [])
        cache_callback.assert_not_called()
        request.assert_called_once()
        save_cache.assert_called_once_with("noble", "sv", [])

    def test_emits_stale_cache_before_reporting_network_failure(self):
        cached_data = [{
            "name": "ubuntu-example",
            "translated_pct": 75.0,
            "untranslated": 25,
            "need_review": 0,
            "changed": 0,
            "total": 100,
            "last_edited": "",
            "last_editor": "",
            "translate_url": "https://translations.launchpad.net/ubuntu-example",
        }]
        session = Mock()
        session.headers = {}
        cache_callback = Mock()

        with (
            patch.object(scraper, "load_cache", return_value=(cached_data, 1200.0)),
            patch.object(scraper.time, "time", return_value=8400.0),
            patch.object(scraper.requests, "Session", return_value=session),
            patch.object(scraper, "_request_with_retry", side_effect=requests.ConnectionError("offline")),
        ):
            with self.assertRaises(requests.ConnectionError):
                scraper.fetch_all_packages("noble", "sv", cache_cb=cache_callback)

        packages, age_minutes = cache_callback.call_args.args
        self.assertEqual([package.name for package in packages], ["ubuntu-example"])
        self.assertEqual(age_minutes, 120)

    def test_total_count_accepts_grouped_digits(self):
        html = '<table><tr><td class="batch-navigation-index">1 to 300 of 1,234 results</td></tr></table>'
        self.assertEqual(scraper.get_total_count(html), 1234)

    def test_fetches_every_page_when_total_uses_thousands_separator(self):
        first_page = '<table><tr><td class="batch-navigation-index">1 to 300 of 1,234 results</td></tr></table>'
        session = Mock()
        session.headers = {}
        package = scraper.PackageStats(
            name="example", translated_pct=100.0, untranslated=0,
            need_review=0, changed=0, total=1, last_edited="",
            last_editor="", translate_url="https://translations.launchpad.net/example",
        )
        responses = [Mock(text=first_page)] + [Mock(text="<html></html>") for _ in range(4)]
        expected_urls = [scraper.get_lang_url("noble", "sv", 300, start) for start in (0, 300, 600, 900, 1200)]

        with (
            patch.object(scraper.requests, "Session", return_value=session),
            patch.object(scraper, "_request_with_retry", side_effect=responses) as request,
            patch.object(scraper, "parse_page", side_effect=[[package]] + [[] for _ in range(4)]),
            patch.object(scraper, "save_cache") as save_cache,
            patch.object(scraper.time, "sleep"),
        ):
            result = scraper.fetch_all_packages("noble", "sv", force=True)

        self.assertEqual(result, [package])
        self.assertEqual([call.args[1] for call in request.call_args_list], expected_urls)
        save_cache.assert_called_once_with("noble", "sv", [scraper._packages_to_dicts([package])[0]])


class LaunchpadPackageParsingTests(unittest.TestCase):
    def test_parse_page_accepts_grouped_package_counts(self):
        html = """<table class="translation-stats"><tr id="ubuntu-example">
          <td><a href="/ubuntu/noble/+source/example">example</a></td>
          <td><span class="sortkey">50</span>50%</td>
          <td><span class="sortkey">1,234</span>1,234</td>
          <td><span class="sortkey">2 345</span>2 345</td>
          <td><span class="sortkey">3</span>3</td>
          <td>1,234</td><td><time>today</time></td><td><a>Translator</a></td>
        </tr></table>"""

        [package] = scraper.parse_page(html, "noble")

        self.assertEqual(package.untranslated, 1234)
        self.assertEqual(package.need_review, 2345)
        self.assertEqual(package.changed, 3)
        self.assertEqual(package.total, 1234)
        self.assertEqual(package.translated, 0)


if __name__ == "__main__":
    unittest.main()
