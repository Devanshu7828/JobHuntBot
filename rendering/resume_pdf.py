"""
Resume PDF Renderer — generates an ATS-friendly resume PDF
from a structured resume dict using reportlab.

Why reportlab (not WeasyPrint):
- Pure Python, no system dependencies
- Works on Windows without GTK installs
- ATS-friendly text extraction
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


# Colors
ACCENT = HexColor("#1a3c6e")
DARK = HexColor("#2c2c2c")
GRAY = HexColor("#555555")
LINK = HexColor("#1565c0")


def _styles():
    base = getSampleStyleSheet()
    return {
        "name":     ParagraphStyle(
            "name", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=18, textColor=ACCENT, alignment=TA_CENTER, leading=22
        ),
        "title":    ParagraphStyle(
            "title", parent=base["Normal"], fontName="Helvetica",
            fontSize=10, textColor=GRAY, alignment=TA_CENTER, leading=12
        ),
        "contact":  ParagraphStyle(
            "contact", parent=base["Normal"], fontName="Helvetica",
            fontSize=8, textColor=DARK, alignment=TA_CENTER, leading=10
        ),
        "section":  ParagraphStyle(
            "section", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=10, textColor=ACCENT, alignment=TA_LEFT, leading=12,
            spaceBefore=8, spaceAfter=2
        ),
        "body":     ParagraphStyle(
            "body", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.5, textColor=DARK, alignment=TA_LEFT, leading=11
        ),
        "role":     ParagraphStyle(
            "role", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9.5, textColor=DARK, alignment=TA_LEFT, leading=11
        ),
        "duration": ParagraphStyle(
            "duration", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=8, textColor=GRAY, alignment=TA_LEFT, leading=10
        ),
        "bullet":   ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=8.5, textColor=DARK, alignment=TA_LEFT, leading=10.5,
            leftIndent=8, bulletIndent=0
        ),
    }


def render_resume_pdf(resume: dict, output_path: str) -> str:
    """Render a resume dict to PDF and return the saved path."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm,
        topMargin=12*mm, bottomMargin=12*mm,
    )
    s = _styles()
    story = []

    # ─── HEADER ────────────────────────────────────────────────
    contact = resume.get("contact", {})
    story.append(Paragraph(resume["name"].upper(), s["name"]))
    story.append(Paragraph(resume.get("title", ""), s["title"]))
    contact_line = " &nbsp;|&nbsp; ".join(filter(None, [
        contact.get("phone", ""),
        contact.get("email", ""),
        contact.get("location", ""),
    ]))
    story.append(Paragraph(contact_line, s["contact"]))
    links_line = " &nbsp;|&nbsp; ".join(filter(None, [
        contact.get("linkedin", ""),
        contact.get("github", ""),
    ]))
    if links_line:
        story.append(Paragraph(links_line, s["contact"]))

    story.append(Spacer(1, 4))

    def section_header(title):
        story.append(Spacer(1, 4))
        story.append(Paragraph(title.upper(), s["section"]))
        story.append(HRFlowable(
            width="100%", thickness=0.7, color=ACCENT,
            spaceBefore=1, spaceAfter=3
        ))

    # ─── SUMMARY ───────────────────────────────────────────────
    if resume.get("summary"):
        section_header("Professional Summary")
        story.append(Paragraph(resume["summary"], s["body"]))

    # ─── SKILLS ────────────────────────────────────────────────
    if resume.get("skills"):
        section_header("Technical Skills")
        skill_labels = {
            "automation": "Automation",
            "languages": "Languages & DB",
            "frameworks": "Frameworks",
            "api": "API Testing",
            "cicd": "CI / DevOps",
            "reporting": "Reporting",
            "testing_types": "Test Types",
            "tools": "Tools",
            "domain": "Domain",
            "methodology": "Methodology",
        }
        for key, label in skill_labels.items():
            if key in resume["skills"] and resume["skills"][key]:
                line = f"<b>{label}:</b> {' &nbsp;|&nbsp; '.join(resume['skills'][key])}"
                story.append(Paragraph(line, s["body"]))

    # ─── EXPERIENCE ────────────────────────────────────────────
    if resume.get("experience"):
        section_header("Professional Experience")
        for exp in resume["experience"]:
            story.append(Paragraph(exp.get("title", ""), s["role"]))
            meta = f"{exp.get('duration','')}  |  {exp.get('company','')}, {exp.get('location','')}"
            if exp.get("client"):
                meta += f"  |  {exp['client']}"
            story.append(Paragraph(meta, s["duration"]))
            story.append(Spacer(1, 2))
            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"\u2022 &nbsp;{bullet}", s["bullet"]))
            story.append(Spacer(1, 4))

    # ─── PROJECTS ──────────────────────────────────────────────
    if resume.get("projects"):
        section_header("Automation Framework (Personal)")
        for proj in resume["projects"]:
            line = f"<b>{proj.get('name','')}</b>  —  {proj.get('url','')}"
            story.append(Paragraph(line, s["body"]))
            story.append(Paragraph(proj.get("description", ""), s["body"]))

    # ─── EDUCATION ─────────────────────────────────────────────
    if resume.get("education"):
        section_header("Education")
        edu = resume["education"]
        story.append(Paragraph(
            f"<b>{edu.get('degree','')}</b>  ({edu.get('year','')})", s["body"]
        ))
        story.append(Paragraph(
            f"{edu.get('institution','')}  |  {edu.get('grade','')}", s["body"]
        ))

    # ─── CERTS & AWARDS ────────────────────────────────────────
    if resume.get("certifications") or resume.get("awards"):
        section_header("Certifications & Awards")
        for cert in resume.get("certifications", []):
            story.append(Paragraph(f"\u2022 &nbsp;{cert}", s["bullet"]))
        for award in resume.get("awards", []):
            story.append(Paragraph(f"\u2022 &nbsp;{award}", s["bullet"]))

    doc.build(story)
    return output_path


def render_cover_letter_pdf(text: str, output_path: str) -> str:
    """Render plain-text cover letter as a clean PDF."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )
    s = _styles()
    story = []
    for paragraph in text.split("\n\n"):
        if paragraph.strip():
            # Convert markdown-style bold (**x**) to HTML <b>
            html = paragraph.strip().replace("**", "<b>", 1)
            count = html.count("<b>")
            while "**" in html:
                html = html.replace("**", "</b>", 1) if count % 2 else html.replace("**", "<b>", 1)
                count += 1
            story.append(Paragraph(html.replace("\n", "<br/>"), s["body"]))
            story.append(Spacer(1, 6))
    doc.build(story)
    return output_path
