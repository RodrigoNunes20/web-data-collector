import unittest

from collector.github import fetch_repos, to_row
from collector.http import FetchError


def repo(name, stars=0, fork=False, language="Python", **extra):
    return {
        "name": name,
        "description": extra.get("description"),
        "language": language,
        "stargazers_count": stars,
        "forks_count": extra.get("forks", 0),
        "open_issues_count": extra.get("issues", 0),
        "updated_at": "2026-05-01T10:20:30Z",
        "fork": fork,
        "html_url": f"https://github.com/user/{name}",
    }


class GitHubTests(unittest.TestCase):
    def test_to_row_handles_missing_values(self):
        row = to_row({"name": "x", "description": None, "language": None, "stargazers_count": None})
        self.assertEqual(row["description"], "")
        self.assertEqual(row["language"], "")
        self.assertEqual(row["stars"], 0)
        self.assertFalse(row["is_fork"])

    def test_pagination_and_sorting(self):
        pages = {
            1: [repo("b", 5), repo("a", 5)],
            2: [repo("c", 50)],
        }
        calls = []

        def get_json(url, params=None):
            calls.append(params["page"])
            return pages[params["page"]]

        rows = fetch_repos(get_json, "user", per_page=2)
        self.assertEqual(calls, [1, 2])
        self.assertEqual([r["name"] for r in rows], ["c", "a", "b"])  # stars desc, then name
        self.assertEqual(rows[0]["updated_at"], "2026-05-01")

    def test_stops_after_max_pages(self):
        calls = []

        def get_json(url, params=None):
            calls.append(params["page"])
            return [repo(f"r{params['page']}a"), repo(f"r{params['page']}b")]

        fetch_repos(get_json, "user", per_page=2, max_pages=3)
        self.assertEqual(calls, [1, 2, 3])

    def test_skip_forks(self):
        def get_json(url, params=None):
            return [repo("mine", 1), repo("copied", 99, fork=True)]

        rows = fetch_repos(get_json, "user", include_forks=False)
        self.assertEqual([r["name"] for r in rows], ["mine"])

    def test_unexpected_payload(self):
        with self.assertRaises(ValueError):
            fetch_repos(lambda url, params=None: {"message": "Not Found"}, "user")

    def test_fetch_errors_propagate(self):
        def get_json(url, params=None):
            raise FetchError("HTTP 404")

        with self.assertRaises(FetchError):
            fetch_repos(get_json, "nobody")


if __name__ == "__main__":
    unittest.main()
