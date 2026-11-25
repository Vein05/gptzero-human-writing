"""Download pages politely, keeping every response in an on-disk cache.

The cache folder is $COLLECT_CACHE (default .cache); a file is named by the SHA-1 of its URL, so a cache filled once
makes every later run offline. With COLLECT_OFFLINE=1 a page missing from the cache raises NotCached instead of being
downloaded. The User-Agent comes from $COLLECT_USER_AGENT; SEC EDGAR asks for a name and an email address in it, so
sec.gov requests use $SEC_USER_AGENT. Requests are spaced 1.5 s apart ($COLLECT_PAUSE_SECONDS), SEC requests 0.25 s.
"""

import hashlib
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

PAUSE_SECONDS = {"sec.gov": 0.25}
DEFAULT_PAUSE = 1.5
TRIES = 4


class NotCached(LookupError):
    pass


def cache_dir():
    return Path(os.environ.get("COLLECT_CACHE", ".cache"))


def cache_path(url):
    return cache_dir() / hashlib.sha1(url.encode()).hexdigest()


def user_agent(url):
    if "sec.gov" in url:
        return os.environ["SEC_USER_AGENT"]
    return os.environ.get("COLLECT_USER_AGENT", "research-script")


def pause_for(url):
    default = float(os.environ.get("COLLECT_PAUSE_SECONDS", DEFAULT_PAUSE))
    return next((s for host, s in PAUSE_SECONDS.items() if host in url), default)


def fetch(url):
    """Return the body of `url` as bytes, from the cache when it is there; None for a page that does not exist."""
    path = cache_path(url)
    if path.exists():
        return path.read_bytes()
    if os.environ.get("COLLECT_OFFLINE"):
        raise NotCached(url)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent(url), "Accept-Encoding": "identity"})
    for attempt in range(TRIES):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == TRIES - 1:
                raise
        except urllib.error.URLError:
            if attempt == TRIES - 1:
                raise
        time.sleep(30 * (attempt + 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    time.sleep(pause_for(url))
    return body
