"""
Cover Letter Generator — template-based, no LLM required.

Produces a tailored 200-250 word cover letter using:
- Candidate profile (from base_resume.json)
- Job details (title, company, matched skills, JD highlights)

For higher quality, this module can be swapped with an LLM-based version
later by changing only the `generate()` method signature.
"""
from datetime import date


COVER_TEMPLATE = """{date}

Dear {company} Hiring Team,

I am writing to express my strong interest in the **{job_title}** role at {company}. With {experience_years}+ years of end-to-end QA experience at Amdocs across Telecom Billing, AR, Collections, and CSM, I bring a proven track record of delivering high-quality releases under tight timelines.

In my most recent role as a Senior Test Engineer, I am leading QA for the WBPM PH3 program covering 3,200+ test cases with a 7-8 engineer team. Prior to that, I led the Rainbow Project at Rogers Telecom — 1,200+ test scenarios, on-time delivery, and management recognition for zero critical production escapes.

I noticed your JD emphasises **{top_skills_csv}** — these align directly with my hands-on expertise. My personal Selenium + Java + TestNG + Maven framework on GitHub demonstrates my automation skills beyond manual testing, and I am actively expanding into REST Assured and CI/CD pipelines.

What draws me to {company} specifically is the opportunity to apply rigorous test engineering to {value_prop}. I am confident I can contribute from day one and grow with the team.

I would welcome the chance to discuss how my background in telecom QA, team leadership, and automation can support {company}'s quality goals.

Sincerely,
{name}
{email}  |  {phone}
{linkedin}  |  {github}
"""


# Domain-specific value propositions (tailored intros)
VALUE_PROPS = {
    "fintech":     "financial-grade reliability and compliance",
    "banking":     "transaction integrity and regulatory testing",
    "ecommerce":   "high-traffic platform stability and checkout reliability",
    "e-commerce":  "high-traffic platform stability and checkout reliability",
    "healthcare":  "HIPAA-aligned, safety-critical software testing",
    "saas":        "rapid release cycles with strong regression safety nets",
    "telecom":     "complex billing and provisioning workflows (my core domain)",
    "product":     "shipping high-quality, customer-facing features quickly",
    "startup":     "wearing multiple hats and building QA culture from ground up",
}


def detect_value_prop(jd_text: str) -> str:
    """Pick the most relevant value prop based on JD keywords."""
    jd_lower = jd_text.lower()
    for keyword, prop in VALUE_PROPS.items():
        if keyword in jd_lower:
            return prop
    return "delivering robust, well-tested software at scale"


def generate_cover_letter(
    job,
    candidate: dict,
    base_resume: dict,
    output_path: str = None,
) -> str:
    """Generate a tailored cover letter as plain text."""
    top_skills = job.matched_skills[:5] if job.matched_skills else ["Selenium", "Java", "TestNG"]
    top_skills_csv = ", ".join(top_skills)

    value_prop = detect_value_prop(job.description or job.title)

    letter = COVER_TEMPLATE.format(
        date=date.today().strftime("%d %B %Y"),
        company=job.company,
        job_title=job.title,
        experience_years=candidate.get("experience_years", 5),
        top_skills_csv=top_skills_csv,
        value_prop=value_prop,
        name=candidate["name"],
        email=candidate["email"],
        phone=candidate["phone"],
        linkedin=candidate["linkedin"],
        github=candidate["github"],
    )

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(letter)

    return letter
