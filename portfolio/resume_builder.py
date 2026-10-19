"""
Builds one portfolio's resume.

collect() gathers the content once; render_pdf()/render_docx() turn it into an
ATS-friendly file (single column, real selectable text, standard fonts, plain
section headings, no tables, icons or images), and render_pages() turns the PDF
into page images for the read-only viewer, which has no text layer to copy.
"""
import hashlib
import io
import json
import re
import unicodedata
from datetime import date

import pymupdf
from django.core.cache import cache
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, FrameBreak, HRFlowable, KeepInFrame, KeepTogether,
    NextPageTemplate, PageTemplate, Paragraph, SimpleDocTemplate, Spacer,
)

from .resume_text import LEVELS, level_for, link as _link, p as _p, pdf_safe as _pdf_safe, short_url as _short_url  # noqa: F401

CACHE_SECONDS = 3600

# The resume designs the owner can pick from. "formats" are the files each can
# be saved as: the designed layout is PDF only because Word does not hold a
# coloured header, sidebar and skill bars faithfully.
TEMPLATES = {
    # --- plain, ATS-safe: one column of real text, no tables / images / icons ---
    "ats": {"group": "ats", "label": "ATS standard", "formats": ["pdf", "docx"],
            "blurb": "The safest all-rounder: clean sans-serif, left aligned, ruled headings."},
    "classic": {"group": "ats", "label": "Classic", "formats": ["pdf", "docx"],
                "blurb": "Traditional serif with a centred header and double rules. Formal, academic or senior roles."},
    "compact": {"group": "ats", "label": "Compact", "formats": ["pdf", "docx"],
                "blurb": "Tighter type with dates on the same line, to keep a long history on one page."},
    "executive": {"group": "ats", "label": "Executive", "formats": ["pdf", "docx"],
                  "blurb": "Serif with a large name and navy headings. Management and senior roles."},
    "technical": {"group": "ats", "label": "Technical", "formats": ["pdf", "docx"],
                  "blurb": "Monospace with dashed rules. Developer and engineering roles."},
    # --- drawn layouts: PDF only (Word cannot hold them faithfully) ---
    "modern": {"group": "graphic", "label": "Modern", "formats": ["pdf"],
               "blurb": "Navy header with your photo, light sidebar and skill bars, orange accents."},
    "midnight": {"group": "graphic", "label": "Midnight", "formats": ["pdf"],
                 "blurb": "Dark sidebar topped by a large round photo, teal accents, skill bars."},
    "banner": {"group": "graphic", "label": "Banner", "formats": ["pdf"],
               "blurb": "Teal banner with a square photo, details column on the right, level dots."},
    "timeline": {"group": "graphic", "label": "Timeline", "formats": ["pdf"],
                 "blurb": "Photo beside the name, experience on a vertical timeline, skills as tags, purple accents."},
    "elegant": {"group": "graphic", "label": "Elegant", "formats": ["pdf"],
                "blurb": "Charcoal and gold: your photo as a framed portrait, a fine header rule and a tinted side card for skills and education."},
}
DEFAULT_TEMPLATE = "ats"
VIEWER_TEMPLATE = "modern"   # what a visitor sees in the read-only viewer: it is for people, not parsers


def _month_year(day):
    return f"{day.month:02d}/{day.year}"


def _period(start, end, today, *, months):
    """'09/2022 - 10/2022' (or years only), with 'Present' while the end date is still ahead."""
    ongoing = end > today
    fmt = _month_year if months else (lambda d: str(d.year))
    return f"{fmt(start)} – {'Present' if ongoing else fmt(end)}"


def _bullets(text):
    """A description becomes bullet points: one per line (a leading dash/dot is ignored)."""
    lines = [re.sub(r"^[\-•*\s]+", "", line).strip() for line in (text or "").splitlines()]
    return [line for line in lines if line]


def _file_part(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "Resume"


def collect(track, site_url):
    """Everything the resume says, from one portfolio, as plain data."""
    today = date.today()
    profile = track.profile
    user = profile.user
    about = getattr(track, "about", None)

    name = f"{user.first_name} {user.last_name}".strip() or user.username
    years = about.years_of_experience if about else 0
    headline = (about.skill if about else "") or track.name
    if years >= 1:
        headline = f"{headline} | {years}+ years of experience"

    contact = [part for part in (track.email, track.phone_number, track.location) if part]
    links = [("Portfolio", f"{site_url.rstrip('/')}/{track.slug}")]
    for label, url in (("LinkedIn", track.linkedin), ("GitHub", track.github)):
        if url:
            links.append((label, url))

    experience, education, skills, certificates, ratings = [], [], {}, [], []
    if about:
        for job in sorted(about.resume.all(), key=lambda r: (r.end_year, r.start_year), reverse=True):
            experience.append({
                "title": job.post, "company": job.company_name,
                "period": _period(job.start_year, job.end_year, today, months=True),
                "bullets": _bullets(job.description),
            })
            if job.certificate_link:
                certificates.append((f"{job.post}, {job.company_name}", job.certificate_link))
        for school in sorted(about.school.all(), key=lambda s: (s.end_year, s.start_year), reverse=True):
            education.append({
                "school": school.school_name, "degree": school.degree,
                "period": _period(school.start_year, school.end_year, today, months=False),
                "bullets": _bullets(school.description),
            })
            if school.certificate_link:
                certificates.append((school.school_name, school.certificate_link))
        for skill in sorted(about.proficiency.all(), key=lambda p: (-p.skill_range, p.skill_name)):
            skills.setdefault(level_for(skill.skill_range), []).append(skill.skill_name)
            ratings.append((skill.skill_name, skill.skill_range))
            if skill.certificate_link:
                certificates.append((skill.skill_name, skill.certificate_link))

    projects = [
        {"name": item.name, "category": item.category, "link": item.project_link,
         "description": item.description.strip(), "thumbnail": item.thumbnail}
        for item in track.items.all()
    ]

    return {
        "today": today.isoformat(),
        "name": name,
        "portfolio": track.name,
        "headline": headline,
        "photo_url": track.display_pic or profile.display_pic,
        "contact": contact,
        "links": links,
        "summary": (about.description if about else "").strip(),
        "experience": experience,
        "education": education,
        # strongest first, in the order of LEVELS
        "skills": [(label, skills[label]) for _, label in LEVELS if label in skills],
        "skill_ratings": ratings,   # strongest first, for the designed layout's bars
        "projects": projects,
        "certificates": certificates,
    }


def file_stem(data, template=DEFAULT_TEMPLATE):
    stem = f"{_file_part(data['name'])}_{_file_part(data['portfolio'])}_Resume"
    return stem if template == DEFAULT_TEMPLATE else f"{stem}_{template.capitalize()}"


def digest(data):
    return hashlib.sha1(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- PDF --------

def _bottom_border(paragraph):
    """A thin line under a heading (a Word paragraph border)."""
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "111111")):
        bottom.set(qn(key), value)
    borders.append(bottom)
    paragraph._p.get_or_add_pPr().append(borders)


def _hyperlink(paragraph, url, text):
    r_id = paragraph.part.relate_to(
        url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True
    )
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run, props = OxmlElement("w:r"), OxmlElement("w:rPr")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    colour = OxmlElement("w:color")
    colour.set(qn("w:val"), "1A4FA0")
    props.append(colour)
    props.append(underline)
    label = OxmlElement("w:t")
    label.text = text
    label.set(qn("xml:space"), "preserve")
    run.append(props)
    run.append(label)
    link.append(run)
    paragraph._p.append(link)


def _docx_document(data, style):
    font, centered, rule = style["font"], style["centered"], style["rule"]
    tight, head_color = style.get("tight", False), style.get("color")
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.left_margin = section.right_margin = Mm(18)
    section.top_margin = section.bottom_margin = Mm(15)

    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = font, Pt(style["size"])
    normal.paragraph_format.space_after = Pt(1 if tight else 2)
    # real Word heading styles are what ATS and screen readers key on
    heading_style = doc.styles["Heading 1"]
    heading_style.font.name, heading_style.font.size = font, Pt(11)
    heading_style.font.bold = True
    heading_style.font.color.rgb = RGBColor.from_string(head_color) if head_color else RGBColor(0x11, 0x11, 0x11)
    heading_style.paragraph_format.space_before, heading_style.paragraph_format.space_after = (Pt(6), Pt(2)) if tight else (Pt(10), Pt(3))

    props = doc.core_properties
    props.title, props.author, props.subject = f"{data['name']} - Resume", data["name"], data["headline"]

    title = doc.add_paragraph(style="Title")
    run = title.add_run(data["name"])
    run.font.size, run.font.bold, run.font.name = Pt(style["name_size"]), True, font
    run.font.color.rgb = RGBColor(0x11, 0x11, 0x11)
    align = WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.LEFT
    title.alignment = align
    doc.add_paragraph(data["headline"]).alignment = align
    if data["contact"]:
        doc.add_paragraph("  |  ".join(data["contact"])).alignment = align
    if data["links"]:
        links = doc.add_paragraph()
        links.alignment = align
        for index, (label, url) in enumerate(data["links"]):
            links.add_run(("  |  " if index else "") + f"{label}: ")
            _hyperlink(links, url, url)

    def heading(text):
        paragraph = doc.add_heading(text, level=1)
        if centered:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if rule:
            _bottom_border(paragraph)

    def role(left, right, dates):
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(5)
        paragraph.paragraph_format.keep_with_next = True
        paragraph.add_run(f"{left} | {right}" if right else left).bold = True
        meta = doc.add_paragraph(dates)
        meta.paragraph_format.keep_with_next = True
        meta.runs[0].font.size = Pt(9.5)
        meta.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    if data["summary"]:
        heading("PROFESSIONAL SUMMARY")
        doc.add_paragraph(data["summary"])
    if data["skills"]:
        heading("SKILLS")
        for label, names in data["skills"]:
            line = doc.add_paragraph()
            line.add_run(f"{label}: ").bold = True
            line.add_run(", ".join(names))
    if data["experience"]:
        heading("PROFESSIONAL EXPERIENCE")
        for job in data["experience"]:
            role(job["title"], job["company"], job["period"])
            for text in job["bullets"]:
                doc.add_paragraph(text, style="List Bullet")
    if data["education"]:
        heading("EDUCATION")
        for school in data["education"]:
            role(school["degree"] or school["school"], school["school"] if school["degree"] else "", school["period"])
            for text in school["bullets"]:
                doc.add_paragraph(text, style="List Bullet")
    if data["projects"]:
        heading("PROJECTS")
        for project in data["projects"]:
            line = doc.add_paragraph(style="List Bullet")
            line.add_run(project["name"]).bold = True
            line.add_run(f" ({project['category']}): ")
            _hyperlink(line, project["link"], project["link"])
            if project["description"]:   # optional: a plain line under the link, no picture
                line.add_run().add_break()
                line.add_run(project["description"])
    if data["certificates"]:
        heading("CERTIFICATES")
        for label, url in data["certificates"]:
            line = doc.add_paragraph(style="List Bullet")
            line.add_run(f"{label}: ")
            _hyperlink(line, url, url)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------- the other designs ---------

# ----------------------------------------------- the five plain (ATS) designs -----

# Plain designs differ only in the ways a parser does not care about: typeface,
# alignment, density, how headings are drawn, and where dates sit. Every one is a
# single column of real text with no tables, images or icons.
PLAIN_STYLES = {
    "ats": dict(font="Helvetica", bold="Helvetica-Bold", italic="Helvetica-Oblique", size=10, leading=13.5, name_size=21,
                align="left", head="rule", accent="#111111", date="below", job="title_company", margin_x=18, margin_y=15, space=1.0),
    "classic": dict(font="Times-Roman", bold="Times-Bold", italic="Times-Italic", size=10.5, leading=14, name_size=24,
                    align="center", head="double", accent="#1a1a1a", date="below", job="company_title", margin_x=20, margin_y=16, space=1.0),
    "compact": dict(font="Helvetica", bold="Helvetica-Bold", italic="Helvetica-Oblique", size=9.2, leading=11.9, name_size=18,
                    align="left", head="rule", accent="#111111", date="inline", job="title_company", margin_x=14, margin_y=12, space=0.55),
    "executive": dict(font="Times-Roman", bold="Times-Bold", italic="Times-Italic", size=10.5, leading=14.5, name_size=27,
                      align="left", head="color", accent="#1f3a5f", date="below", job="title_company", margin_x=20, margin_y=18, space=1.15),
    "technical": dict(font="Courier", bold="Courier-Bold", italic="Courier-Oblique", size=8.6, leading=12, name_size=17,
                      align="left", head="dashed", accent="#111111", date="below", job="title_company", margin_x=16, margin_y=14, space=0.9),
}

DOCX_STYLES = {
    "ats": dict(font="Calibri", size=10.5, centered=False, rule=False, name_size=21),
    "classic": dict(font="Times New Roman", size=11, centered=True, rule=True, name_size=22),
    "compact": dict(font="Arial", size=9.5, centered=False, rule=False, name_size=17, tight=True),
    "executive": dict(font="Georgia", size=11, centered=False, rule=True, name_size=25, color="1F3A5F"),
    "technical": dict(font="Consolas", size=9, centered=False, rule=False, name_size=16),
}


def _pdf_plain(data, style):
    sp = style["space"]
    ink, grey, accent = colors.HexColor("#1a1a1a"), colors.HexColor("#555555"), colors.HexColor(style["accent"])
    align = TA_CENTER if style["align"] == "center" else TA_LEFT
    base = ParagraphStyle("base", fontName=style["font"], fontSize=style["size"], leading=style["leading"], textColor=ink)
    st = {
        "name": ParagraphStyle("name", parent=base, fontName=style["bold"], fontSize=style["name_size"], leading=style["name_size"] * 1.18,
                               alignment=align, textColor=accent if style["head"] == "color" else ink),
        "headline": ParagraphStyle("headline", parent=base, fontName=style["italic"] if style["font"] != "Helvetica" else style["font"],
                                   fontSize=style["size"] + 1.5, leading=style["leading"] + 2, alignment=align, textColor=grey, spaceAfter=3 * sp),
        "contact": ParagraphStyle("contact", parent=base, fontSize=style["size"] - 0.5, alignment=align),
        "h": ParagraphStyle("h", parent=base, fontName=style["bold"], fontSize=style["size"] + 1, leading=style["leading"] + 1,
                            spaceBefore=9 * sp, alignment=align, textColor=accent if style["head"] == "color" else ink),
        "role": ParagraphStyle("role", parent=base, spaceBefore=4 * sp),
        "meta": ParagraphStyle("meta", parent=base, fontSize=style["size"] - 1, textColor=grey,
                               fontName=style["italic"] if style["font"] == "Times-Roman" else style["font"]),
        "bullet": ParagraphStyle("bullet", parent=base, leftIndent=12, bulletIndent=2, spaceBefore=1 * sp),
    }

    def heading(title):
        rules = {
            "rule": [HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#999999"), spaceBefore=1, spaceAfter=3 * sp)],
            "double": [HRFlowable(width="100%", thickness=1, color=ink, spaceBefore=1, spaceAfter=1),
                       HRFlowable(width="100%", thickness=0.3, color=ink, spaceBefore=0, spaceAfter=4 * sp)],
            "color": [HRFlowable(width="100%", thickness=1.2, color=accent, spaceBefore=1, spaceAfter=3 * sp)],
            "dashed": [HRFlowable(width="100%", thickness=0.7, color=ink, dash=(3, 2), spaceBefore=1, spaceAfter=3 * sp)],
        }[style["head"]]
        return [Paragraph(title, st["h"])] + rules

    def bullet(text):
        return Paragraph(_p(text), st["bullet"], bulletText="\u2022")

    def entry(first, second, period, bullets):
        """first / second: the two halves of the heading line, in this design's order."""
        if style["job"] == "company_title" and second:
            line = f"<b>{_p(second)}</b>, <i>{_p(first)}</i>"
        else:
            line = f"<b>{_p(first)}</b>" + (f" | {_p(second)}" if second else "")
        if style["date"] == "inline":
            return KeepTogether([Paragraph(f"{line} | {_p(period)}", st["role"])] + [bullet(b) for b in bullets])
        return KeepTogether([Paragraph(line, st["role"]), Paragraph(_p(period), st["meta"])] + [bullet(b) for b in bullets])

    story = [Paragraph(_p(data["name"]), st["name"]), Paragraph(_p(data["headline"]), st["headline"])]
    if data["contact"]:
        story.append(Paragraph(_p("  |  ".join(data["contact"])), st["contact"]))
    if data["links"]:
        story.append(Paragraph("  |  ".join(f"{_p(label)}: {_link(url)}" for label, url in data["links"]), st["contact"]))

    if data["summary"]:
        story += heading("PROFESSIONAL SUMMARY") + [Paragraph(_p(data["summary"]), base)]
    if data["skills"]:
        story += heading("SKILLS")
        story += [Paragraph(f"<b>{_p(label)}:</b> {_p(', '.join(names))}", base) for label, names in data["skills"]]
    if data["experience"]:
        story += heading("PROFESSIONAL EXPERIENCE")
        story += [entry(job["title"], job["company"], job["period"], job["bullets"]) for job in data["experience"]]
    if data["education"]:
        story += heading("EDUCATION")
        for school in data["education"]:
            story.append(entry(school["degree"] or school["school"], school["school"] if school["degree"] else "", school["period"], school["bullets"]))
    if data["projects"]:
        story += heading("PROJECTS")
        for project in data["projects"]:
            note = f"<br/>{_p(project['description'])}" if project["description"] else ""
            story.append(Paragraph(f"<b>{_p(project['name'])}</b> ({_p(project['category'])}): {_link(project['link'])}{note}", st["bullet"], bulletText="\u2022"))
    if data["certificates"]:
        story += heading("CERTIFICATES")
        for label, url in data["certificates"]:
            story.append(Paragraph(f"{_p(label)}: {_link(url)}", st["bullet"], bulletText="\u2022"))

    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=style["margin_x"] * mm, rightMargin=style["margin_x"] * mm,
        topMargin=style["margin_y"] * mm, bottomMargin=style["margin_y"] * mm,
        title=f"{data['name']} - Resume", author=data["name"], subject=data["headline"],
    ).build(story)
    return buffer.getvalue()


def render_pdf(data, template=DEFAULT_TEMPLATE):
    if template in PLAIN_STYLES:
        return _pdf_plain(data, PLAIN_STYLES[template])
    from . import resume_graphics
    return resume_graphics.DESIGNS[template](data)


def render_docx(data, template=DEFAULT_TEMPLATE):
    if template not in DOCX_STYLES:
        raise ValueError(f"The {template} design is not available as a Word file")
    return _docx_document(data, DOCX_STYLES[template])


# -------------------------------------------------- read-only page images -----

def render_pages(pdf_bytes, dpi=130, first_only=False):
    """One PNG per PDF page. They carry no text layer, so there is nothing to
    select or copy; a small footer marks them as a preview copy."""
    pages = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            rect = page.rect
            page.insert_text(
                pymupdf.Point(rect.width / 2 - 38, rect.height - 16), "Read-only preview",
                fontsize=7.5, color=(0.62, 0.62, 0.62),
            )
            pages.append(page.get_pixmap(dpi=dpi).tobytes("png"))
            if first_only:
                break
    return pages


# ----------------------------------------------------------- cached access ----

def cached(kind, track, data, template=DEFAULT_TEMPLATE):
    """The file for this exact content, design and day ('Present' depends on it); edits change the key.
    kind: pdf | docx | pages (all page images) | thumb (first page, small, for the picker)."""
    key = f"resume:{kind}:{template}:{track.pk}:{digest(data)}"
    if kind == "pages":
        return cache.get_or_set(key, lambda: render_pages(cached("pdf", track, data, template)), CACHE_SECONDS)
    if kind == "thumb":
        return cache.get_or_set(key, lambda: render_pages(cached("pdf", track, data, template), dpi=48, first_only=True)[0], CACHE_SECONDS)
    if kind == "pdf":
        return cache.get_or_set(key, lambda: render_pdf(data, template), CACHE_SECONDS)
    return cache.get_or_set(key, lambda: render_docx(data, template), CACHE_SECONDS)
