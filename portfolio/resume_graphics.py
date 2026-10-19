"""
The drawn resume designs (PDF only): five layouts, each with the owner's photo
(or their initials when there is none) in a different place.

  modern    navy header, photo in the header's right, light sidebar on the left
  midnight  dark sidebar topped by a large round photo, name in the main column
  banner    teal banner with a square photo on its left, details column on the right
  timeline  photo beside the name, one column, experience on a vertical timeline
  elegant   charcoal and gold: framed portrait, hairline header, a tinted side card

They are for sending to a person, not to an online form: the text is real text,
but the layout is not built for a parser (see the plain designs for that).
"""
import io
from concurrent.futures import ThreadPoolExecutor

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, FrameBreak, HRFlowable, KeepInFrame, KeepTogether,
    NextPageTemplate, PageTemplate, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from .resume_photo import fetch_photo, fetch_thumbnails
from .resume_text import level_for, link, p, pdf_safe, short_url

PAGE_W, PAGE_H = A4


def _hex(value):
    return colors.HexColor(value)


def _name_font(name, width, start=25, floor=14):
    size = start
    while stringWidth(name, "Helvetica-Bold", size) > width and size > floor:
        size -= 1
    return size


class _Portrait:
    """The owner's picture, drawn as a circle or a rounded square - or, when there
    is no usable picture, their initials in the same shape, so a layout never has a hole."""

    def __init__(self, data):
        raw = fetch_photo(data.get("photo_url"))
        self.reader = ImageReader(io.BytesIO(raw)) if raw else None
        self.initials = "".join(word[0] for word in data["name"].split()[:2]).upper() or "?"

    def draw(self, canvas, x, y, size, shape="circle", ring=None, ring_width=1.2 * mm, fallback=None):
        radius = size / 2

        def outline():
            path = canvas.beginPath()
            if shape == "circle":
                path.circle(x + radius, y + radius, radius)
            else:
                path.roundRect(x, y, size, size, size * 0.13)
            return path

        canvas.saveState()
        path = outline()
        if self.reader:
            canvas.clipPath(path, stroke=0, fill=0)
            canvas.drawImage(self.reader, x, y, size, size, mask=None)
        else:
            canvas.setFillColor(fallback or colors.HexColor("#8a94a6"))
            canvas.drawPath(path, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", size * 0.36)
            canvas.drawCentredString(x + radius, y + radius - size * 0.125, self.initials)
        canvas.restoreState()
        if ring is not None:
            canvas.saveState()
            canvas.setStrokeColor(ring)
            canvas.setLineWidth(ring_width)
            canvas.drawPath(outline(), stroke=1, fill=0)
            canvas.restoreState()

    def draw_framed(self, canvas, x, y, width, height, frame, offset=2.4 * mm, fallback=None):
        """A tall rounded portrait with an outlined frame set behind it, shifted down and to the right."""
        radius = width * 0.08
        canvas.saveState()
        canvas.setStrokeColor(frame)
        canvas.setLineWidth(1.1)
        canvas.roundRect(x + offset, y - offset, width, height, radius, stroke=1, fill=0)
        path = canvas.beginPath()
        path.roundRect(x, y, width, height, radius)
        if self.reader:
            canvas.clipPath(path, stroke=0, fill=0)
            side = max(width, height)   # the picture is square: cover the tall box, cropping the sides
            canvas.drawImage(self.reader, x - (side - width) / 2, y - (side - height) / 2, side, side, mask=None)
        else:
            canvas.setFillColor(fallback or colors.HexColor("#8a94a6"))
            canvas.drawPath(path, stroke=0, fill=1)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", width * 0.34)
            canvas.drawCentredString(x + width / 2, y + height / 2 - width * 0.12, self.initials)
        canvas.restoreState()


# ------------------------------------------------------------- flowables ------

class _Bar(Flowable):
    """A skill's name, its level in words and a bar filled to its 0-100 rating."""

    def __init__(self, name, rating, width, ink, muted, track, fill):
        super().__init__()
        self.name, self.rating, self.width, self.height = name, rating, width, 8.6 * mm
        self.ink, self.muted, self.track, self.fill = ink, muted, track, fill

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFont("Helvetica", 9)
        c.setFillColor(self.ink)
        c.drawString(0, 4.9 * mm, self.name)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(self.muted)
        c.drawRightString(self.width, 4.9 * mm, level_for(self.rating))
        c.setFillColor(self.track)
        c.roundRect(0, 1.3 * mm, self.width, 1.9 * mm, 0.95 * mm, stroke=0, fill=1)
        c.setFillColor(self.fill)
        c.roundRect(0, 1.3 * mm, max(1.9 * mm, self.width * self.rating / 100), 1.9 * mm, 0.95 * mm, stroke=0, fill=1)


class _Dots(Flowable):
    """A skill's name with five dots filled to its rating (each dot is 20 points)."""

    def __init__(self, name, rating, width, ink, muted, fill, empty):
        super().__init__()
        self.name, self.rating, self.width, self.height = name, rating, width, 6.2 * mm
        self.ink, self.muted, self.fill, self.empty = ink, muted, fill, empty

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFont("Helvetica", 9)
        c.setFillColor(self.ink)
        c.drawString(0, 1.6 * mm, self.name)
        filled = max(1, round(self.rating / 20))
        for i in range(5):
            c.setFillColor(self.fill if i < filled else self.empty)
            c.circle(self.width - (4 - i) * 4.1 * mm - 1.3 * mm, 2.4 * mm, 1.35 * mm, stroke=0, fill=1)


class _Chips(Flowable):
    """Skills as rounded tags that wrap onto as many lines as they need.
    Expert = filled, Advanced = outlined, the rest = tinted."""

    def __init__(self, items, width, accent, ink, tint):
        super().__init__()
        self.items, self.width, self.accent, self.ink, self.tint = items, width, accent, ink, tint
        self.size, self.pad, self.gap, self.row_h = 8.4, 2.6 * mm, 1.8 * mm, 6.2 * mm
        self._lines = None

    def _layout(self, width):
        lines, line, x = [], [], 0
        for name, rating in self.items:
            w = stringWidth(pdf_safe(name), "Helvetica", self.size) + 2 * self.pad
            if line and x + w > width:
                lines.append(line)
                line, x = [], 0
            line.append((name, rating, x, w))
            x += w + self.gap
        if line:
            lines.append(line)
        return lines

    def wrap(self, available_width, available_height):
        self._lines = self._layout(self.width)
        self.height = max(1, len(self._lines)) * (self.row_h + 1.6 * mm)
        return self.width, self.height

    def draw(self):
        c = self.canv
        for row, line in enumerate(self._lines):
            y = self.height - (row + 1) * (self.row_h + 1.6 * mm) + 1.6 * mm
            for name, rating, x, w in line:
                label = level_for(rating)
                if label == "Expert":
                    c.setFillColor(self.accent)
                    c.roundRect(x, y, w, self.row_h, self.row_h / 2, stroke=0, fill=1)
                    c.setFillColor(colors.white)
                elif label == "Advanced":
                    c.setStrokeColor(self.accent)
                    c.setLineWidth(0.9)
                    c.roundRect(x, y, w, self.row_h, self.row_h / 2, stroke=1, fill=0)
                    c.setFillColor(self.ink)
                else:
                    c.setFillColor(self.tint)
                    c.roundRect(x, y, w, self.row_h, self.row_h / 2, stroke=0, fill=1)
                    c.setFillColor(self.ink)
                c.setFont("Helvetica", self.size)
                c.drawString(x + self.pad, y + 1.9 * mm, pdf_safe(name))


class _TimelineItem(Flowable):
    """One entry on a vertical timeline: a dot, the entry beside it, and a line down to the next."""
    INDENT = 7 * mm

    def __init__(self, content, width, accent, line, last=False):
        super().__init__()
        self.content, self.width, self.accent, self.line, self.last = content, width, accent, line, last

    def wrap(self, available_width, available_height):
        inner = self.width - self.INDENT
        self._sizes = [f.wrap(inner, available_height) for f in self.content]
        self.height = sum(h for _, h in self._sizes) + 3.2 * mm
        return self.width, self.height

    def draw(self):
        c = self.canv
        if not self.last:
            c.setStrokeColor(self.line)
            c.setLineWidth(1.1)
            c.line(2 * mm, self.height - 4 * mm, 2 * mm, 0)
        c.setFillColor(self.accent)
        c.circle(2 * mm, self.height - 3.2 * mm, 1.7 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.circle(2 * mm, self.height - 3.2 * mm, 0.6 * mm, stroke=0, fill=1)
        y = self.height
        for flowable, (_, h) in zip(self.content, self._sizes):
            y -= h
            flowable.drawOn(c, self.INDENT, y)


def _tracked(canvas, x, y, text, font, size, color, space):
    """Draw one line of text with extra space between the letters."""
    line = canvas.beginText(x, y)
    line.setFont(font, size)
    line.setFillColor(color)
    line.setCharSpace(space)
    line.textOut(text)
    canvas.drawText(line)


class _Spaced(Flowable):
    """One line of small capitals-style text with the letters spaced out; shrinks to fit its width."""

    def __init__(self, text, width, font, size, color, space=1.4, after=0):
        super().__init__()
        self.text, self.width, self.font, self.color, self.after = pdf_safe(text), width, font, color, after
        self.size, self.space = size, space

    def wrap(self, available_width, available_height):
        while self.size > 6 and stringWidth(self.text, self.font, self.size) + self.space * len(self.text) > self.width:
            self.size -= 0.5
        self.height = self.size + 3 + self.after
        return self.width, self.height

    def draw(self):
        _tracked(self.canv, 0, self.after, self.text, self.font, self.size, self.color, self.space)


class _Section(Flowable):
    """A section title: spaced capitals with a short accent rule beneath."""

    def __init__(self, title, width, ink, accent):
        super().__init__()
        self.title, self.width, self.ink, self.accent = title, width, ink, accent

    def wrap(self, available_width, available_height):
        self.height = 11 * mm
        return self.width, self.height

    def draw(self):
        c = self.canv
        _tracked(c, 0, 3.4 * mm, self.title, "Helvetica-Bold", 9, self.ink, 1.7)
        c.setFillColor(self.accent)
        c.rect(0, 1.2 * mm, 9 * mm, 0.7 * mm, stroke=0, fill=1)


class _Gauge(Flowable):
    """A skill: its name, its level in words, and a fine line with a dot at the rating."""

    def __init__(self, name, rating, width, ink, muted, track, fill):
        super().__init__()
        self.name, self.rating, self.width, self.height = pdf_safe(name), rating, width, 8.2 * mm
        self.ink, self.muted, self.track, self.fill = ink, muted, track, fill

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        c = self.canv
        label = level_for(self.rating)
        c.setFont("Helvetica", 8.8)
        c.setFillColor(self.ink)
        c.drawString(0, self.height - 3.4 * mm, self.name)
        c.setFont("Helvetica", 7.4)
        c.setFillColor(self.muted)
        c.drawRightString(self.width, self.height - 3.4 * mm, label)
        y, reach = 1.6 * mm, self.width * self.rating / 100
        c.setStrokeColor(self.track)
        c.setLineWidth(0.9)
        c.line(0, y, self.width, y)
        c.setStrokeColor(self.fill)
        c.setLineWidth(1.4)
        c.line(0, y, reach, y)
        c.setFillColor(self.fill)
        c.circle(reach, y, 1.1 * mm, stroke=0, fill=1)


class _ProjectCard(Flowable):
    """A project: its thumbnail beside the name and category, an optional short
    description and the link. It takes whatever width it is given, so it reads the
    same in a narrow column or across a full page. With no usable thumbnail it
    shows a plain tile carrying the project's first letter."""
    THUMB_W, THUMB_H, GAP, AFTER = 30 * mm, 22.5 * mm, 4 * mm, 3.4 * mm

    def __init__(self, project, picture, styles, accent, link_color, tile):
        super().__init__()
        self.project, self.styles, self.accent, self.link_color, self.tile = project, styles, accent, link_color, tile
        self.reader = ImageReader(io.BytesIO(picture)) if picture else None

    def wrap(self, available_width, available_height):
        project, st = self.project, self.styles
        inner = available_width - self.THUMB_W - self.GAP
        self._parts = [Paragraph(f"<b>{p(project['name'])}</b>  <font size='7.2' color='{self.link_color}'>{p(project['category']).upper()}</font>",
                                 ParagraphStyle("pc_name", parent=st["base"], fontSize=10, leading=13))]
        if project["description"]:
            self._parts.append(Paragraph(p(project["description"]), ParagraphStyle("pc_text", parent=st["meta"], leading=11.4, spaceBefore=1)))
        self._parts.append(Paragraph(link(project["link"], short_url(project["link"], 46), self.link_color), ParagraphStyle("pc_link", parent=st["small"], spaceBefore=1.5)))
        self._sizes = [part.wrap(inner, available_height)[1] for part in self._parts]
        self.width = available_width
        self.height = max(self.THUMB_H, sum(self._sizes)) + self.AFTER
        return self.width, self.height

    def draw(self):
        c = self.canv
        top = self.height
        y = top - self.THUMB_H
        c.saveState()
        path = c.beginPath()
        path.roundRect(0, y, self.THUMB_W, self.THUMB_H, 1.6 * mm)
        if self.reader:
            c.clipPath(path, stroke=0, fill=0)
            c.drawImage(self.reader, 0, y, self.THUMB_W, self.THUMB_H, mask=None)
        else:
            c.setFillColor(_hex(self.tile))
            c.drawPath(path, stroke=0, fill=1)
            c.setFillColor(_hex(self.accent))
            c.setFont("Helvetica-Bold", 20)
            c.drawCentredString(self.THUMB_W / 2, y + self.THUMB_H / 2 - 7, (self.project["name"][:1] or "?").upper())
        c.restoreState()
        c.saveState()
        c.setStrokeColor(_hex(self.tile))
        c.setLineWidth(0.6)
        c.roundRect(0, y, self.THUMB_W, self.THUMB_H, 1.6 * mm, stroke=1, fill=0)
        c.restoreState()
        c.linkURL(self.project["link"], (0, y, self.THUMB_W, top), relative=1)   # the picture opens the project too
        x = self.THUMB_W + self.GAP
        for part, h in zip(self._parts, self._sizes):
            top -= h
            part.drawOn(c, x, top)


def _project_cards(data, st, accent, link_color, tile):
    """One card per project; the thumbnails are fetched together, and cached."""
    pictures = fetch_thumbnails([project["thumbnail"] for project in data["projects"]])
    return [_ProjectCard(project, pictures.get(project["thumbnail"]), st, accent, link_color, tile) for project in data["projects"]]


# ------------------------------------------------------- shared text blocks ----

def _styles(ink, muted, accent):
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=ink)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8.8, leading=12),
        "meta": ParagraphStyle("meta", parent=base, fontSize=8.8, textColor=muted),
        "role": ParagraphStyle("role", parent=base, fontName="Helvetica-Bold", fontSize=10.5, textColor=ink),
        "bullet": ParagraphStyle("bullet", parent=base, leftIndent=11, bulletIndent=1, spaceBefore=1, bulletColor=accent),
    }


def _bullets(bullets, style):
    return [Paragraph(p(text), style, bulletText="•") for text in bullets]


def _frame(x, y, w, h):
    return Frame(x, y, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)


# ----------------------------------------------------------- sidebar engine ----

SIDEBAR_THEMES = {
    # photo: where the portrait goes - the header's right, the sidebar's top, or the banner's left
    "modern": dict(side="left", side_bg="#eef1f6", dark=False, band="#17233a", band_h=36, band_ink="#ffffff", band_sub="#ffcf99",
                   accent="#ff8c06", ink="#1b2230", muted="#5b6577", track="#d5dae4", skills="bars", photo="band_right", ring="#ffffff"),
    "midnight": dict(side="left", side_bg="#12263f", dark=True, band=None, band_h=0, band_ink="#ffffff", band_sub="#5eead4",
                     accent="#14b8a6", ink="#1b2230", muted="#5b6577", track="#24415f", skills="bars", photo="sidebar_top", ring="#14b8a6"),
    "banner": dict(side="right", side_bg="#eef6f4", dark=False, band="#0f766e", band_h=44, band_ink="#ffffff", band_sub="#b5ece3",
                   accent="#0f766e", ink="#13302c", muted="#4f6b66", track="#cfe4df", skills="dots", photo="band_left", ring="#ffffff"),
}


def _sidebar(data, theme_key):
    t = SIDEBAR_THEMES[theme_key]
    portrait = _Portrait(data)
    accent, ink, muted = _hex(t["accent"]), _hex(t["ink"]), _hex(t["muted"])
    side_ink = _hex("#e8eef7") if t["dark"] else ink
    side_muted = _hex("#9fb4cc") if t["dark"] else muted
    side_head = _hex(t["band_sub"]) if t["dark"] else _hex("#17233a" if theme_key == "modern" else t["accent"])
    link_color = "#8ecbff" if t["dark"] else "#1a4fa0"
    band_h = t["band_h"] * mm
    side_w, margin = 66 * mm, 8 * mm
    left = t["side"] == "left"
    side_x0 = 0 if left else PAGE_W - side_w
    photo_top = 12 * mm + 40 * mm + 8 * mm if t["photo"] == "sidebar_top" else 0
    side_top = PAGE_H - (band_h + 8 * mm if t["band"] else photo_top)
    main_top = PAGE_H - (band_h + 8 * mm if t["band"] else 14 * mm)
    side_h, main_h = side_top - 10 * mm, main_top - 10 * mm
    side_frame_w = side_w - 2 * margin + 2 * mm
    side_frame_x = side_x0 + margin - 1 * mm
    main_x, main_w = (side_w + 8 * mm, PAGE_W - side_w - 18 * mm) if left else (12 * mm, PAGE_W - side_w - 20 * mm)
    name_x = 54 * mm if t["photo"] == "band_left" else 12 * mm
    name_room = PAGE_W - name_x - 12 * mm - (34 * mm if t["photo"] == "band_right" else 0)
    name_size = _name_font(data["name"], name_room)

    def first_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(_hex(t["side_bg"]))
        canvas.rect(side_x0, 0, side_w, PAGE_H - band_h, stroke=0, fill=1)
        if t["band"]:
            canvas.setFillColor(_hex(t["band"]))
            canvas.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)
            canvas.setFillColor(accent if theme_key == "modern" else _hex("#14b8a6"))
            canvas.rect(0, PAGE_H - band_h - 1.4 * mm, PAGE_W, 1.4 * mm, stroke=0, fill=1)
            canvas.setFillColor(_hex(t["band_ink"]))
            canvas.setFont("Helvetica-Bold", name_size)
            canvas.drawString(name_x, PAGE_H - band_h / 2 + 2 * mm, pdf_safe(data["name"]))
            canvas.setFillColor(_hex(t["band_sub"]))
            canvas.setFont("Helvetica", 11.5)
            canvas.drawString(name_x, PAGE_H - band_h / 2 - 7 * mm, pdf_safe(data["headline"])[:80])
        canvas.restoreState()
        ring = _hex(t["ring"])
        if t["photo"] == "band_right":
            portrait.draw(canvas, PAGE_W - 12 * mm - 26 * mm, PAGE_H - band_h / 2 - 13 * mm, 26 * mm, "circle", ring, fallback=accent)
        elif t["photo"] == "band_left":
            portrait.draw(canvas, 12 * mm, PAGE_H - band_h / 2 - 17 * mm, 34 * mm, "round", ring, fallback=_hex("#14b8a6"))
        else:
            portrait.draw(canvas, side_w / 2 - 20 * mm, PAGE_H - 12 * mm - 40 * mm, 40 * mm, "circle", ring, ring_width=1.6 * mm, fallback=accent)

    def later_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(_hex(t["band"] or t["side_bg"]))
        canvas.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, stroke=0, fill=1)
        canvas.setFillColor(accent)
        canvas.rect(0, PAGE_H - 15.2 * mm, PAGE_W, 1.2 * mm, stroke=0, fill=1)
        canvas.setFillColor(_hex(t["band_ink"]))
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(14 * mm, PAGE_H - 9 * mm, pdf_safe(data["name"]))
        canvas.restoreState()

    st = _styles(ink, muted, accent)
    side_small = ParagraphStyle("side_small", parent=st["small"], textColor=side_ink)
    side_meta = ParagraphStyle("side_meta", parent=st["meta"], textColor=side_muted)
    side_h_style = ParagraphStyle("side_h", parent=st["base"], fontName="Helvetica-Bold", fontSize=9.5, textColor=side_head, spaceBefore=9, spaceAfter=1)
    main_h_style = ParagraphStyle("main_h", parent=st["base"], fontName="Helvetica-Bold", fontSize=11, textColor=accent, spaceBefore=8, spaceAfter=1)

    def rule(width="100%", thickness=1.4):
        return HRFlowable(width=width, thickness=thickness, color=accent, spaceBefore=1, spaceAfter=4, hAlign="LEFT")

    side = [Paragraph("CONTACT", side_h_style), rule("30%")]
    side += [Paragraph(p(item), side_small) for item in data["contact"]]
    side += [
        Paragraph(f"<b>{p(label)}</b><br/>{link(url, short_url(url, 34), link_color)}", side_small)
        for label, url in data["links"]
    ]
    if data["skill_ratings"]:
        side += [Paragraph("SKILLS", side_h_style), rule("30%")]
        for name, rating in data["skill_ratings"][:10]:
            if t["skills"] == "bars":
                side.append(_Bar(pdf_safe(name), rating, side_frame_w, side_ink, side_muted, _hex(t["track"]), accent))
            else:
                side.append(_Dots(pdf_safe(name), rating, side_frame_w, side_ink, side_muted, accent, _hex(t["track"])))
        rest = [name for name, _ in data["skill_ratings"][10:]]
        if rest:
            side.append(Paragraph(f"<b>Also:</b> {p(', '.join(rest))}", side_small))
    if data["education"]:
        side += [Paragraph("EDUCATION", side_h_style), rule("30%")]
        for school in data["education"]:
            side.append(Paragraph(f"<b>{p(school['school'])}</b>", side_small))
            if school["degree"]:
                side.append(Paragraph(p(school["degree"]), side_small))
            side.append(Paragraph(p(school["period"]), side_meta))
            side.append(Spacer(1, 3))
    if data["certificates"]:
        side += [Paragraph("CERTIFICATES", side_h_style), rule("30%")]
        side += [Paragraph(p(label), side_small) for label, _ in data["certificates"]]

    main = []
    if not t["band"]:   # no header band: the name leads the main column
        main += [
            Paragraph(p(data["name"]), ParagraphStyle("nm", parent=st["base"], fontName="Helvetica-Bold", fontSize=name_size + 3, leading=name_size + 8, textColor=ink)),
            Paragraph(p(data["headline"]), ParagraphStyle("hl", parent=st["base"], fontSize=11.5, leading=15, textColor=accent, spaceAfter=4)),
        ]
    if data["summary"]:
        main += [Paragraph("PROFILE", main_h_style), rule("12%"), Paragraph(p(data["summary"]), st["base"])]
    if data["experience"]:
        main += [Paragraph("EXPERIENCE", main_h_style), rule("12%")]
        for job in data["experience"]:
            block = [Paragraph(p(job["title"]), ParagraphStyle("r", parent=st["role"], spaceBefore=5)),
                     Paragraph(f"{p(job['company'])}  \u00b7  {p(job['period'])}", st["meta"])]
            main.append(KeepTogether(block + _bullets(job["bullets"], st["bullet"])))
    if data["projects"]:
        main += [Paragraph("PROJECTS", main_h_style), rule("12%")]
        main += _project_cards(data, st, t["accent"], "#1a4fa0", t["side_bg"])

    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, title=f"{data['name']} - Resume", author=data["name"], subject=data["headline"])
    doc.addPageTemplates([
        PageTemplate("first", onPage=first_page, frames=[
            _frame(side_frame_x, 10 * mm, side_frame_w, side_h),
            _frame(main_x, 10 * mm, main_w, main_h),
        ]),
        PageTemplate("later", onPage=later_page, frames=[_frame(14 * mm, 10 * mm, PAGE_W - 28 * mm, PAGE_H - 15.2 * mm - 8 * mm - 10 * mm)]),
    ])
    # the sidebar shrinks to fit its column rather than spilling into the main one
    doc.build([KeepInFrame(side_frame_w, side_h, side, mode="shrink"), FrameBreak(), NextPageTemplate("later")] + main)
    return buffer.getvalue()


# ---------------------------------------------------------------- timeline -----

def _timeline(data):
    portrait = _Portrait(data)
    accent, ink, muted = _hex("#6d28d9"), _hex("#1f1b2e"), _hex("#6b6580")
    line, tint = _hex("#d9d2ee"), _hex("#ece8f8")
    left, right, photo = 22 * mm, 16 * mm, 32 * mm
    width = PAGE_W - left - right
    head_top = PAGE_H - 14 * mm
    st = _styles(ink, muted, accent)

    def first_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(accent)
        canvas.rect(0, PAGE_H - 4 * mm, PAGE_W, 4 * mm, stroke=0, fill=1)
        canvas.restoreState()
        portrait.draw(canvas, 16 * mm, head_top - photo, photo, "circle", accent, ring_width=1.4 * mm, fallback=accent)

    def later_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(accent)
        canvas.rect(0, PAGE_H - 4 * mm, PAGE_W, 4 * mm, stroke=0, fill=1)
        canvas.restoreState()

    heading = ParagraphStyle("h", parent=st["base"], fontName="Helvetica-Bold", fontSize=11, textColor=accent, spaceBefore=10, spaceAfter=1)

    def head(title):
        return [Paragraph(title, heading), HRFlowable(width="100%", thickness=0.7, color=line, spaceBefore=1, spaceAfter=5)]

    header = [
        Paragraph(p(data["name"]), ParagraphStyle("nm", parent=st["base"], fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=ink)),
        Paragraph(p(data["headline"]), ParagraphStyle("hl", parent=st["base"], fontSize=11.5, leading=15, textColor=accent, spaceAfter=4)),
    ]
    if data["contact"]:
        header.append(Paragraph(p("  \u2022  ".join(data["contact"])), st["small"]))
    if data["links"]:
        header.append(Paragraph("  \u2022  ".join(f"{p(label)}: {link(url, short_url(url, 34), '#4c1d95')}" for label, url in data["links"]), st["small"]))

    story = []
    if data["summary"]:
        story += head("PROFILE") + [Paragraph(p(data["summary"]), st["base"])]
    if data["skill_ratings"]:
        story += head("SKILLS")
        story.append(_Chips(data["skill_ratings"], width, accent, ink, tint))
    if data["experience"]:
        story += head("EXPERIENCE")
        for index, job in enumerate(data["experience"]):
            content = [Paragraph(p(job["title"]), st["role"]),
                       Paragraph(f"{p(job['company'])}  \u00b7  {p(job['period'])}", st["meta"])] + _bullets(job["bullets"], st["bullet"])
            story.append(_TimelineItem(content, width, accent, line, last=index == len(data["experience"]) - 1))
    if data["education"]:
        story += head("EDUCATION")
        for index, school in enumerate(data["education"]):
            # one line each (school, what was studied, years) so a long CV stays on one page
            parts = [f"<b>{p(school['school'])}</b>"] + ([p(school["degree"])] if school["degree"] else [])
            content = [Paragraph("  \u00b7  ".join(parts) + f"  <font color='#6b6580'>{p(school['period'])}</font>", st["small"])]
            story.append(_TimelineItem(content, width, accent, line, last=index == len(data["education"]) - 1))
    if data["projects"]:
        story += head("PROJECTS")
        story += _project_cards(data, st, "#6d28d9", "#4c1d95", "#ece8f8")
    if data["certificates"]:
        story += head("CERTIFICATES")
        story += [Paragraph(f"{p(label)}: {link(url, short_url(url), '#4c1d95')}", st["bullet"], bulletText="\u2022") for label, url in data["certificates"]]

    head_x = 16 * mm + photo + 7 * mm
    head_w, head_h = PAGE_W - head_x - right, photo + 2 * mm
    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, title=f"{data['name']} - Resume", author=data["name"], subject=data["headline"])
    doc.addPageTemplates([
        PageTemplate("first", onPage=first_page, frames=[
            _frame(head_x, head_top - head_h, head_w, head_h),
            _frame(left, 12 * mm, width, head_top - head_h - 6 * mm - 12 * mm),
        ]),
        PageTemplate("later", onPage=later_page, frames=[_frame(left, 12 * mm, width, PAGE_H - 12 * mm - 14 * mm)]),
    ])
    doc.build([KeepInFrame(head_w, head_h, header, mode="shrink"), FrameBreak(), NextPageTemplate("later")] + story)
    return buffer.getvalue()


# ----------------------------------------------------------------- elegant -----

def _elegant(data):
    portrait = _Portrait(data)
    ink, muted, gold = _hex("#1f2933"), _hex("#6b7280"), _hex("#b08236")
    gold_text, card, track = "#8a5f17", _hex("#f6f2ea"), _hex("#e2d9c8")
    margin, gap, photo_w, photo_h = 14 * mm, 8 * mm, 32 * mm, 40 * mm
    width = PAGE_W - 2 * margin
    card_w = 62 * mm
    main_w = width - card_w - gap
    head_top = PAGE_H - 13 * mm
    rule_y = head_top - photo_h - 5.5 * mm
    body_top = rule_y - 5 * mm
    card_pad = 5 * mm
    st = _styles(ink, muted, gold)
    small = ParagraphStyle("small", parent=st["small"], textColor=ink)
    card_meta = ParagraphStyle("card_meta", parent=st["meta"], fontSize=8.2)

    def first_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ink)
        canvas.rect(0, PAGE_H - 3 * mm, PAGE_W, 3 * mm, stroke=0, fill=1)
        canvas.setStrokeColor(gold)
        canvas.setLineWidth(0.9)
        canvas.line(margin, rule_y, PAGE_W - margin, rule_y)
        canvas.setFillColor(card)
        canvas.roundRect(PAGE_W - margin - card_w, 10 * mm, card_w, body_top - 10 * mm, 3 * mm, stroke=0, fill=1)
        canvas.restoreState()
        portrait.draw_framed(canvas, margin, head_top - photo_h, photo_w, photo_h, gold, fallback=ink)

    def later_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ink)
        canvas.rect(0, PAGE_H - 3 * mm, PAGE_W, 3 * mm, stroke=0, fill=1)
        _tracked(canvas, margin, PAGE_H - 11 * mm, pdf_safe(data["name"]).upper(), "Helvetica", 8, muted, 1.2)
        canvas.setStrokeColor(gold)
        canvas.setLineWidth(0.6)
        canvas.line(margin, PAGE_H - 13.5 * mm, PAGE_W - margin, PAGE_H - 13.5 * mm)
        canvas.restoreState()

    def section(title, w=main_w):
        return _Section(title, w, ink, gold)

    def two_cols(left_html, right_html, left_style, right_style, split=0.74):
        table = Table([[Paragraph(left_html, left_style), Paragraph(right_html, right_style)]], colWidths=[main_w * split, main_w * (1 - split)])
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                   ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        return table

    head_x = margin + photo_w + 11 * mm
    head_w, head_h = PAGE_W - margin - head_x, photo_h
    header = [
        Spacer(1, 3 * mm),
        Paragraph(p(data["name"]), ParagraphStyle("nm", parent=st["base"], fontName="Helvetica-Bold", fontSize=_name_font(data["name"], head_w, 31, 18), leading=37, textColor=ink)),
        Spacer(1, 1.2 * mm),
        _Spaced(data["headline"].upper(), head_w, "Helvetica-Bold", 8.8, _hex(gold_text), space=1.3, after=2 * mm),
    ]
    if data["contact"]:
        header.append(Paragraph(p("   \u2022   ".join(data["contact"])), small))
    if data["links"]:
        header.append(Spacer(1, 1 * mm))
        header.append(Paragraph("   \u2022   ".join(f"{p(label)} {link(url, short_url(url, 30), gold_text)}" for label, url in data["links"]), small))

    right_w = card_w - 2 * card_pad
    side = []
    if data["skill_ratings"]:
        side += [section("SKILLS", right_w), Spacer(1, 1 * mm)]
        side += [_Gauge(name, rating, right_w, ink, muted, track, gold) for name, rating in data["skill_ratings"]]
    if data["education"]:
        side += [section("EDUCATION", right_w)]
        for school in data["education"]:
            side.append(Paragraph(f"<b>{p(school['school'])}</b>", small))
            if school["degree"]:
                side.append(Paragraph(p(school["degree"]), small))
            side += [Paragraph(p(school["period"]), card_meta), Spacer(1, 2.4 * mm)]
    if data["certificates"]:
        side += [section("CERTIFICATES", right_w)]
        side += [Paragraph(f"{link(url, label, gold_text)}", small) for label, url in data["certificates"]]

    story = []
    if data["summary"]:
        story += [section("PROFILE"), Paragraph(p(data["summary"]), st["base"])]
    if data["experience"]:
        story += [section("EXPERIENCE")]
        date_style = ParagraphStyle("date", parent=st["meta"], alignment=2)
        for job in data["experience"]:
            story.append(KeepTogether([
                two_cols(f"<b>{p(job['title'])}</b>", p(job["period"]), ParagraphStyle("t", parent=st["role"], fontSize=10.5), date_style),
                Paragraph(f"<font color='{gold_text}'><b>{p(job['company'])}</b></font>", small),
                Spacer(1, 1 * mm),
            ] + _bullets(job["bullets"], st["bullet"]) + [Spacer(1, 2.2 * mm)]))
    if data["projects"]:
        story += [section("PROJECTS")]
        story += _project_cards(data, st, gold_text, gold_text, "#f6f2ea")

    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, title=f"{data['name']} - Resume", author=data["name"], subject=data["headline"])
    card_h = body_top - 10 * mm - 2 * card_pad
    doc.addPageTemplates([
        PageTemplate("first", onPage=first_page, frames=[
            _frame(head_x, head_top - head_h, head_w, head_h),
            _frame(PAGE_W - margin - card_w + card_pad, 10 * mm + card_pad, right_w, card_h),
            _frame(margin, 12 * mm, main_w, body_top - 12 * mm),
        ]),
        PageTemplate("later", onPage=later_page, frames=[_frame(margin, 12 * mm, width, PAGE_H - 12 * mm - 20 * mm)]),
    ])
    # the side card shrinks to fit its box rather than spilling out of it
    doc.build([KeepInFrame(head_w, head_h, header, mode="shrink"), FrameBreak(),
               KeepInFrame(right_w, card_h, side, mode="shrink"), FrameBreak(), NextPageTemplate("later")] + story)
    return buffer.getvalue()


def _warm(data):
    """Fetch the photo and every thumbnail at once, so the engines find them in the cache
    instead of waiting for one slow address after another."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        photo = pool.submit(fetch_photo, data.get("photo_url"))
        fetch_thumbnails([project["thumbnail"] for project in data["projects"]])
        photo.result()


def _design(engine):
    def build(data):
        _warm(data)
        return engine(data)
    return build


DESIGNS = {
    "modern": _design(lambda data: _sidebar(data, "modern")),
    "midnight": _design(lambda data: _sidebar(data, "midnight")),
    "banner": _design(lambda data: _sidebar(data, "banner")),
    "timeline": _design(_timeline),
    "elegant": _design(_elegant),
}
