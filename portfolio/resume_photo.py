"""
The pictures for the drawn resume designs: the owner's photo and each project's
thumbnail.

A picture is a web address the owner typed in, so it is fetched with care:
only http(s), only to public addresses (never this machine or a private
network, including after a redirect), a short timeout, a size limit, and it has
to really be an image. Anything wrong just means the design shows the owner's
initials (or a plain tile for a project) instead - a resume is never held up by
a picture.
"""
import hashlib
import io
import ipaddress
import socket
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache
from PIL import Image, ImageOps

MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 6
SIDE = 640                 # the photo is cropped square and shrunk to this
THUMB_SIZE = (480, 360)    # a project thumbnail is cropped to 4:3 and shrunk to this
FOUND_SECONDS = 3600
MISSING_SECONDS = 300      # try again soon if the address was down


def _is_public(host):
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except OSError:
        return False
    return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)


def _check(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or not _is_public(parsed.hostname):
        raise ValueError("not a public web address")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check(newurl)   # every hop must be public too
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(url, fit, centering, quality):
    _check(url)
    opener = urllib.request.build_opener(_CheckedRedirects())
    request = urllib.request.Request(url, headers={"User-Agent": "VectoredMatrix-resume/1.0", "Accept": "image/*"})
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        if not response.headers.get_content_type().startswith("image/"):
            raise ValueError("not an image")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("image too large")
    image = Image.open(io.BytesIO(raw))
    image.load()
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = ImageOps.fit(image, fit, centering=centering)
    out = io.BytesIO()
    image.save(out, "JPEG", quality=quality)
    return out.getvalue()


def _fetch(kind, url, fit, centering, quality):
    if not url:
        return None
    key = f"resume-{kind}:" + hashlib.sha1(url.encode()).hexdigest()
    hit = cache.get(key)
    if hit is not None:
        return hit or None
    try:
        picture = _download(url, fit, centering, quality)
    except Exception:   # any problem at all: the design copes without it
        cache.set(key, b"", MISSING_SECONDS)
        return None
    cache.set(key, picture, FOUND_SECONDS)
    return picture


def fetch_photo(url):
    """The owner's photo as square JPEG bytes, or None when it cannot be used."""
    # faces sit in the upper part of a portrait, so crop square from a little above centre
    return _fetch("photo", url, (SIDE, SIDE), (0.5, 0.3), 88)


def fetch_thumbnail(url):
    """A project thumbnail as 4:3 JPEG bytes, or None when it cannot be used."""
    return _fetch("thumb", url, THUMB_SIZE, (0.5, 0.5), 82)


def fetch_thumbnails(urls):
    """{url: bytes or None} for several thumbnails at once, so one slow address does not stack up."""
    urls = list(dict.fromkeys(u for u in urls if u))
    if not urls:
        return {}
    with ThreadPoolExecutor(max_workers=min(6, len(urls))) as pool:
        return dict(zip(urls, pool.map(fetch_thumbnail, urls)))
