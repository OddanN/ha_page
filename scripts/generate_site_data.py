#!/usr/bin/env python3
"""Generate site data for the GitHub Pages catalog."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64decode
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "site.config.json"
OUTPUT_PATH = ROOT / "data" / "site.generated.json"
API_ROOT = "https://api.github.com"
README_BADGE_LINK_RE = re.compile(
    r"\[!\[(?P<alt>[^]]*)]\((?P<image>[^)]+)\)]\((?P<link>[^)]+)\)"
)
README_BADGE_IMAGE_RE = re.compile(r"!\[(?P<alt>[^]]*)]\((?P<image>[^)]+)\)")


def load_config() -> dict[str, Any]:
    """Load site configuration from the repository root."""
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def github_headers() -> dict[str, str]:
    """Build request headers for GitHub API calls."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ha-page-generator",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def api_get_json(url: str, headers: dict[str, str]) -> Any:
    """Fetch and decode a JSON payload from the given URL."""
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def api_get_optional_json(url: str, headers: dict[str, str]) -> Any | None:
    """Fetch JSON and return None when the resource does not exist."""
    try:
        return api_get_json(url, headers)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def fetch_repositories(username: str) -> list[dict[str, Any]]:
    """Fetch all public repositories for a GitHub user."""
    headers = github_headers()
    repositories: list[dict[str, Any]] = []
    page = 1

    while True:
        query = urllib.parse.urlencode(
            {
                "per_page": 100,
                "page": page,
                "sort": "updated",
                "direction": "desc",
                "type": "public",
            }
        )
        request = urllib.request.Request(
            f"{API_ROOT}/users/{username}/repos?{query}",
            headers=headers,
        )
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not payload:
            break

        repositories.extend(payload)
        page += 1

    return repositories


def fetch_release(owner: str, repo_name: str, headers: dict[str, str]) -> dict[str, Any] | None:
    """Fetch metadata for the latest release of a repository."""
    payload = api_get_optional_json(f"{API_ROOT}/repos/{owner}/{repo_name}/releases/latest", headers)
    if not payload:
        return None

    return {
        "tag_name": payload.get("tag_name"),
        "html_url": payload.get("html_url"),
        "published_at": payload.get("published_at"),
    }


def fetch_logo(owner: str, repo_name: str, headers: dict[str, str]) -> str | None:
    """Return the download URL for the preferred repository logo, if it exists."""
    candidate_paths = [
        f"custom_components/{repo_name}/brand/icon.png",
        "logo.png",
    ]

    for path in candidate_paths:
        payload = api_get_optional_json(f"{API_ROOT}/repos/{owner}/{repo_name}/contents/{path}", headers)
        if payload:
            return payload.get("download_url")

    return None


def fetch_readme_badges(owner: str, repo_name: str, headers: dict[str, str]) -> list[dict[str, str]]:
    """Extract Markdown badges from the top section of the repository README."""
    payload = api_get_optional_json(f"{API_ROOT}/repos/{owner}/{repo_name}/readme", headers)
    if not payload or payload.get("encoding") != "base64":
        return []

    try:
        content = b64decode(payload["content"]).decode("utf-8", errors="ignore")
    except (KeyError, ValueError):
        return []

    snippet = "\n".join(content.splitlines()[:30])
    badges: list[dict[str, str]] = []
    used_images: set[str] = set()

    for match in README_BADGE_LINK_RE.finditer(snippet):
        image_url = match.group("image").strip()
        if image_url in used_images:
            continue
        used_images.add(image_url)
        badges.append(
            {
                "alt": match.group("alt").strip(),
                "image_url": image_url,
                "link_url": match.group("link").strip(),
            }
        )

    for match in README_BADGE_IMAGE_RE.finditer(snippet):
        image_url = match.group("image").strip()
        if image_url in used_images:
            continue
        used_images.add(image_url)
        badges.append(
            {
                "alt": match.group("alt").strip(),
                "image_url": image_url,
                "link_url": "",
            }
        )

    return badges[:4]


def should_ignore_badge(badge: dict[str, str]) -> bool:
    """Return True when a badge should not be shown on the catalog page."""
    image_url = badge.get("image_url", "").lower()
    link_url = badge.get("link_url", "").lower()
    alt = badge.get("alt", "").lower()
    return (
            "my.home-assistant.io" in image_url
            or "my.home-assistant.io" in link_url
            or "open your home assistant instance" in alt
    )


def extract_release_badge(
        badges: list[dict[str, str]],
        owner: str,
        repo_name: str,
) -> tuple[dict[str, str] | None, list[dict[str, str]]]:
    """Split README badges into a dedicated release badge and the remaining badges."""
    release_badge: dict[str, str] | None = None
    filtered: list[dict[str, str]] = []

    for badge in badges:
        if should_ignore_badge(badge):
            continue

        image_url = badge.get("image_url", "").lower()
        alt = badge.get("alt", "").lower()
        link_url = badge.get("link_url", "")
        if release_badge is None and ("github/v/release" in image_url or alt == "github release"):
            release_badge = badge
            continue

        if "github/commit-activity" in image_url and not link_url:
            badge = {
                **badge,
                "link_url": f"https://github.com/{owner}/{repo_name}/commits/main/",
            }

        filtered.append(badge)

    return release_badge, filtered[:4]


def normalize(text: str | None) -> str:
    """Normalize text for case-insensitive filter matching."""
    return (text or "").strip().lower()


def format_repository_name(name: str | None) -> str:
    """Convert a repository slug into a readable title."""
    raw_name = (name or "").strip()
    if not raw_name:
        return ""

    replacements = {
        "home assistant": "Home Assistant",
        "hacs": "HACS",
    }
    lowered = raw_name.lower()
    for suffix, replacement in replacements.items():
        slug_suffix = suffix.replace(" ", "_")
        if lowered.endswith(f"_for_{slug_suffix}"):
            base = raw_name[: -len(f"_for_{slug_suffix}")]
            words = [part.upper() if len(part) <= 4 else part.capitalize() for part in re.split(r"[_-]+", base) if part]
            return f"{' '.join(words)} for {replacement}"

    words = [part.upper() if len(part) <= 4 else part.capitalize() for part in re.split(r"[_-]+", raw_name) if part]
    return " ".join(words)


def repo_matches(repo: dict[str, Any], collection: dict[str, Any]) -> bool:
    """Check whether a repository matches the configured filters."""
    name = normalize(repo.get("name"))
    description = normalize(repo.get("description"))
    topics = [normalize(topic) for topic in repo.get("topics", [])]
    haystack = " ".join(part for part in [name, description, " ".join(topics)] if part)

    include_repositories = {item.lower() for item in collection.get("include_repositories", [])}
    if name in include_repositories:
        return True

    include_topics = {item.lower() for item in collection.get("include_topics", [])}
    if include_topics.intersection(topics):
        return True

    for prefix in collection.get("name_prefixes", []):
        if name.startswith(prefix.lower()):
            return True

    for keyword in collection.get("text_keywords", []):
        if keyword.lower() in haystack:
            return True

    return False


def filter_repositories(repositories: list[dict[str, Any]], collection: dict[str, Any]) -> list[dict[str, Any]]:
    """Filter repositories and enrich them with metadata for rendering."""
    exclude = {item.lower() for item in collection.get("exclude_repositories", [])}
    featured = {item.lower() for item in collection.get("featured_repositories", [])}
    exclude_archived = bool(collection.get("exclude_archived", True))
    exclude_forks = bool(collection.get("exclude_forks", False))
    headers = github_headers()

    filtered: list[dict[str, Any]] = []
    for repo in repositories:
        name = normalize(repo.get("name"))
        if name in exclude:
            continue
        if exclude_archived and repo.get("archived"):
            continue
        if exclude_forks and repo.get("fork"):
            continue
        if not repo_matches(repo, collection):
            continue

        owner = repo.get("owner", {}).get("login")
        readme_badges = fetch_readme_badges(owner, repo.get("name"), headers) if owner else []
        release_badge, readme_badges = extract_release_badge(readme_badges, owner, repo.get("name"))
        filtered.append(
            {
                "name": repo.get("name"),
                "display_name": format_repository_name(repo.get("name")),
                "description": repo.get("description"),
                "html_url": repo.get("html_url"),
                "updated_at": repo.get("updated_at"),
                "language": repo.get("language"),
                "stargazers_count": repo.get("stargazers_count", 0),
                "topics": repo.get("topics", []),
                "fork": bool(repo.get("fork")),
                "archived": bool(repo.get("archived")),
                "featured": name in featured,
                "latest_release": fetch_release(owner, repo.get("name"), headers) if owner else None,
                "release_badge": release_badge,
                "logo_url": fetch_logo(owner, repo.get("name"), headers) if owner else None,
                "readme_badges": readme_badges,
            }
        )

    filtered.sort(
        key=lambda item: (
            not item["featured"],
            -item["stargazers_count"],
            item["name"].lower(),
        )
    )

    max_repositories = int(collection.get("max_repositories", 48))
    return filtered[:max_repositories]


def build_filter_labels(collection: dict[str, Any]) -> list[str]:
    """Build human-readable labels for the configured filters."""
    labels: list[str] = []

    if collection.get("include_topics"):
        labels.append("topics: " + ", ".join(collection["include_topics"]))
    if collection.get("name_prefixes"):
        labels.append("prefixes: " + ", ".join(collection["name_prefixes"]))
    if collection.get("text_keywords"):
        labels.append("keywords: " + ", ".join(collection["text_keywords"]))
    if collection.get("exclude_repositories"):
        labels.append("exclude: " + ", ".join(collection["exclude_repositories"]))

    return labels


def write_output(payload: dict[str, Any]) -> None:
    """Write the generated payload consumed by the frontend."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Generate the site payload from configuration and GitHub metadata."""
    config = load_config()
    site = config["site"]
    collection = config["collection"]

    try:
        repositories = fetch_repositories(site["github_username"])
    except urllib.error.URLError as error:
        print(f"Failed to fetch repositories: {error}", file=sys.stderr)
        return 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site": {
            "title": site["title"],
            "description": site["description"],
            "description_link_label": site.get("description_link_label", ""),
            "description_link_url": site.get("description_link_url", ""),
            "acknowledgements": site.get("acknowledgements", ""),
            "special_thanks": site.get("special_thanks", []),
            "github_profile_url": site["github_profile_url"],
            "source_repository_url": site["source_repository_url"],
        },
        "collection": {
            "filters": build_filter_labels(collection),
        },
        "repos": filter_repositories(repositories, collection),
    }

    write_output(payload)
    print(f"Generated {OUTPUT_PATH} with {len(payload['repos'])} repositories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
