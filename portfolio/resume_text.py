"""Small text helpers shared by the resume designs."""
import re
import unicodedata
from xml.sax.saxutils import escape

# Same bands as the portfolio page (resume.jsx): the owner's 0-100 rating in words.
LEVELS = [(80, "Expert"), (60, "Advanced"), (35, "Intermediate"), (0, "Beginner")]


def level_for(rating):
    return next(label for floor, label in LEVELS if rating >= floor)


def pdf_safe(text):
    """Standard PDF fonts cover Western European text. Each character outside
    that set is simplified on its own (accent dropped, e.g. a dotted O becomes
    O) or shown as ?, rather than turned into a box or an error - and the
    characters that are fine are left exactly as written."""
    text = (text or "").replace("’", "'").replace("“", '"').replace("”", '"')
    out = []
    for char in text:
        try:
            char.encode("cp1252")
            out.append(char)
            continue
        except UnicodeEncodeError:
            pass
        base = "".join(c for c in unicodedata.normalize("NFKD", char) if not unicodedata.combining(c))
        try:
            base.encode("cp1252")
            out.append(base or "?")
        except UnicodeEncodeError:
            out.append("?")
    return "".join(out)


def p(text):
    """Text made safe for a ReportLab paragraph: fonts, and markup shown literally."""
    return escape(pdf_safe(text))


def link(url, text=None, color="#1a4fa0"):
    """A clickable address; the text shown defaults to the address itself."""
    return f'<link href="{escape(pdf_safe(url))}" color="{color}">{escape(pdf_safe(text if text is not None else url))}</link>'


def short_url(url, limit=46):
    text = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
    return text if len(text) <= limit else text[: limit - 1] + "…"
