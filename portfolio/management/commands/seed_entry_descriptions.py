from django.core.management.base import BaseCommand

from portfolio.models import ENTRY_DESCRIPTION_MAX, Proficiency, Resume

# Draft one-liners for the entries that exist today. They are deliberately
# modest: job lines describe the kind of work the title implies, skill lines
# describe the technology itself - nothing claims an achievement. Edit freely
# in the portfolio editor afterwards.
#
# Education entries are intentionally absent: the data only holds a school name
# and dates, so what was studied is the owner's to write.
RESUME_DESCRIPTIONS = {
    ("Robotic Instructor", "Al Izzah"):
        "Taught students the basics of robotics, from sensors and motors to building and programming simple robots.",
    ("Class Teacher", "Al Izzah"):
        "Led a class at Al Izzah, planning lessons and guiding students through the term.",
    ("Full Stack Developer", "Pio Tech"):
        "Building and maintaining full-stack web applications, from the user interface to the server and database.",
    ("Full Stack Developer", "Safe Haven"):
        "Full-stack web development for Safe Haven, building features end to end.",
    ("Block Chain Developer", "Pio Tech"):
        "Blockchain development at Pio Tech, alongside full-stack web work.",
}

SKILL_DESCRIPTIONS = {
    "Python": "General-purpose language for backend services, automation, data work and AI.",
    "JavaScript": "The language of the web: interactive interfaces in the browser and servers with Node.js.",
    "C++": "Fast compiled language for systems, games and performance-critical software.",
    "Rust": "Memory-safe systems language for fast, reliable software.",
    "React Vite": "React with Vite tooling for fast-loading single-page web applications.",
    "React Native": "Cross-platform mobile apps for Android and iOS from one React codebase.",
    "ML and AI": "Machine learning and AI: building and applying models for prediction and automation.",
    "C": "Low-level language for embedded systems and programming close to the hardware.",
    "Solid Works": "3D CAD software for designing mechanical parts and assemblies.",
    "Auto CAD": "2D drafting and 3D design software for technical drawings.",
    "Free CAD": "Open-source parametric 3D modeller for engineering and product design.",
}


class Command(BaseCommand):
    help = (
        "Fill the short description of existing resume and skill entries from the drafts in this file. "
        "Only blank descriptions are touched - anything already written is never overwritten. "
        "Shows what it would do unless run with --apply."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")

    def handle(self, *args, **options):
        apply = options["apply"]
        changed = 0

        for entry in Resume.objects.filter(description="").select_related("about__track"):
            text = RESUME_DESCRIPTIONS.get((entry.post, entry.company_name))
            if text:
                changed += self._set(entry, text, apply, f"{entry.about.track.name} / {entry.post} @ {entry.company_name}")

        for entry in Proficiency.objects.filter(description="").select_related("about__track"):
            text = SKILL_DESCRIPTIONS.get(entry.skill_name)
            if text:
                changed += self._set(entry, text, apply, f"{entry.about.track.name} / skill {entry.skill_name}")

        verb = "Updated" if apply else "Would update (dry run - add --apply to write)"
        self.stdout.write(self.style.SUCCESS(f"{verb}: {changed} entries"))

    def _set(self, entry, text, apply, label):
        assert len(text) <= ENTRY_DESCRIPTION_MAX, f"draft too long for {label}"
        self.stdout.write(f"  {label}: {text}")
        if apply:
            entry.description = text
            entry.save(update_fields=["description"])
        return 1
