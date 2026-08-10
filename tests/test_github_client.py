from __future__ import annotations

import io
import urllib.error
import unittest
from unittest.mock import patch

from project_setup.github import API_BASE, HTTP_TIMEOUT_SECONDS, GitHubClient, GitHubRequestError


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b"{}"


class GitHubClientTests(unittest.TestCase):
    def test_mutation_transport_failure_is_not_retried(self):
        client = GitHubClient("token")
        with patch(
            "project_setup.github.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection lost"),
        ) as urlopen:
            with self.assertRaises(GitHubRequestError):
                client.request_json("POST", f"{API_BASE}/repos/owner/repository/issues", {"title": "Example"})
        self.assertEqual(urlopen.call_count, 1)

    def test_request_uses_finite_timeout(self):
        client = GitHubClient("token")
        with patch("project_setup.github.urllib.request.urlopen", return_value=_Response()) as urlopen:
            self.assertEqual(client.request_json("GET", f"{API_BASE}/repos/owner/repository"), {})
        self.assertEqual(urlopen.call_args.kwargs["timeout"], HTTP_TIMEOUT_SECONDS)

    def test_non_github_api_url_is_rejected_before_opening_connection(self):
        client = GitHubClient("token")
        with patch("project_setup.github.urllib.request.urlopen") as urlopen:
            with self.assertRaisesRegex(ValueError, "Unsupported GitHub API URL"):
                client.request_json("GET", "https://example.com/resource")
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
