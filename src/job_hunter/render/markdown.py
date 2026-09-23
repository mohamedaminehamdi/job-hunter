"""A CV and a letter as markdown.

Written by hand rather than through Jinja, because `render.environment()` turns
autoescaping on for everything - rightly, since it produces HTML - and an
escaped ampersand in a markdown file is a bug with no upside.

This exists so the documents survive a machine with no browser. It also closes
the gap where, if the PDF step failed, the tempting next move would be to let a
model write the markdown instead - which would hand the employers, titles and
dates back to the model and quietly undo the one guarantee this tool makes.
"""

from __future__ import annotations

from ..generate.cover_letter import CoverLetter
from ..profile.models import Personal, Profile
from .html import _long_date, _strip_scheme


def _contact(p: Personal) -> str:
    bits = [p.email, p.phone, ", ".join(x for x in (p.city, p.country) if x)]
    links = [_strip_scheme(x) for x in (p.linkedin, p.github, p.website) if x]
    return " · ".join(x for x in [*bits, *links] if x)


def cv_markdown(document: Profile) -> str:
    """A CV as markdown, in the same order the PDF puts it."""
    out: list[str] = []
    name = document.personal.full_name or "CV"
    out.append(f"# {name}")
    if document.personal.headline:
        out.append(f"*{document.personal.headline}*")
    if contact := _contact(document.personal):
        out.append(contact)
    if document.summary:
        out += ["", document.summary]

    if document.experience:
        out += ["", "## Experience"]
        for role in document.experience:
            where = " — ".join(x for x in (role.company, role.location) if x)
            out += ["", f"### {role.position}" + (f", {where}" if where else "")]
            if role.period:
                out.append(f"*{role.period}*")
            out += [f"- {bullet}" for bullet in role.bullets]

    if document.projects:
        out += ["", "## Projects"]
        for project in document.projects:
            title = f"### {project.name}"
            if project.link:
                title = f"### [{project.name}]({project.link})"
            out += ["", title]
            if project.description:
                out.append(project.description)
            if project.tech:
                out.append(f"*{', '.join(project.tech)}*")

    if document.education:
        out += ["", "## Education"]
        for study in document.education:
            head = ", ".join(x for x in (study.level, study.field_of_study) if x)
            out += ["", f"### {head}" if head else "### Education"]
            line = " · ".join(x for x in (study.institution, study.location,
                                          study.period, study.grade) if x)
            if line:
                out.append(line)
            if study.courses:
                out.append(f"*{', '.join(study.courses)}*")

    if document.skills:
        out += ["", "## Skills", "", " · ".join(document.skills)]

    if document.certifications:
        out += ["", "## Certifications", ""]
        for cert in document.certifications:
            line = " — ".join(x for x in (cert.name, cert.issuer) if x)
            out.append(f"- {line}" + (f" ({cert.year})" if cert.year else ""))

    if document.languages:
        out += ["", "## Languages", "",
                " · ".join(f"{x.name} ({x.level})" if x.level else x.name
                           for x in document.languages)]
    return "\n".join(out).strip() + "\n"


def letter_markdown(letter: CoverLetter) -> str:
    """A cover letter as markdown, ready to paste into a form."""
    out: list[str] = []
    if letter.personal.full_name:
        out.append(f"**{letter.personal.full_name}**")
    if contact := _contact(letter.personal):
        out.append(contact)
    out.append("")
    if letter.company:
        out.append(letter.company)
    if letter.written_on:
        out.append(_long_date(letter.written_on, letter.language))
    if letter.role:
        out += ["", f"**{letter.role}**"]
    out += ["", letter.greeting, ""]
    for paragraph in letter.paragraphs:
        out += [paragraph, ""]
    out.append(letter.closing)
    if letter.signature:
        out += ["", letter.signature]
    return "\n".join(out).strip() + "\n"
