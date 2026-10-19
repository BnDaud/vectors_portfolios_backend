"""
The owner's picture for the drawn resume designs.

The picture is a web address the owner typed in, so it is fetched with care:
only http(s), only to public addresses (never this machine or a private
network, including after a redirect), a short timeout, a size limit, and it has
to really be an image. Anything wrong just means the design shows the owner's
initials instead - a resume is never held up by its photo.
"""
import hashlib
import io
import ipaddress
import socket
import urllib.parse
import urllib.request

from django.core.cache import cache
from PIL import Image, ImageOps

MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 6
SIDE = 640                 # the picture is cropped square and shrunk to this
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


def _download(url):
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
    # faces sit in the upper part of a portrait, so crop square from a little above centre
    image = ImageOps.fit(image, (SIDE, SIDE), centering=(0.5, 0.3))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=88)
    return out.getvalue()


def fetch_photo(url):
    """The picture as square JPEG bytes, or None when it cannot be used."""
    if not url:
        return None
    key = "resume-photo:" + hashlib.sha1(url.encode()).hexdigest()
    hit = cache.get(key)
    if hit is not None:
        return hit or None
    try:
        photo = _download(url)
    except Exception:   # any problem at all: fall back to initials
        cache.set(key, b"", MISSING_SECONDS)
        return None
    cache.set(key, photo, FOUND_SECONDS)
    return photo
