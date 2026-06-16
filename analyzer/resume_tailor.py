"""
Resume Tailor — customizes resume per job description (JD-aware).

Workflow:
1. Build JD text from description + title + skills
2. Tailor title, summary, skill order, and experience bullets
3. Validate via EthicsGuard
4. Return clean tailored dict for PDF generation
"""
import json
import re
import copy
from analyzer.ethics_guard import EthicsGuard


class ResumeTailor:

    JD_SKILL_TERMS = [
        "selenium", "java", "testng", "maven", "rest assured", "api testing",
        "jenkins", "ci/cd", "postman", "jira", "agile", "scrum", "sql",
        "playwright", "cucumber", "bdd", "appium", "python", "docker",
        "kubernetes", "git", "github", "automation", "sdet", "manual testing",
        "regression", "integration", "e2e", "pom", "page object",
        "pandas", "numpy", "power bi", "sql", "scikit-learn", "matplotlib",
        "machine learning", "nlp", "etl", "eda", "dax", "tableau", "excel",
        "data analyst", "data science", "analytics",
    ]

    def __init__(self, base_resume_path: str):
        with open(base_resume_path, "r", encoding="utf-8") as f:
            self.base_resume = json.load(f)
        self.guard = EthicsGuard(self.base_resume)

    def tailor(self, job, base_resume: dict = None) -> tuple:
        base = base_resume or self.base_resume
        candidate = copy.deepcopy(base)
        jd_text = self._build_jd_text(job)

        candidate = self._tailor_title(candidate, job)
        candidate = self._tailor_summary(candidate, job, jd_text)
        candidate = self._reorder_skills(candidate, job, jd_text)
        candidate = self._reorder_experience(candidate, jd_text)
        candidate = self._reorder_projects(candidate, jd_text)

        candidate["tailored_for"] = {
            "company": job.company,
            "title": job.title,
            "platform": job.platform,
            "url": job.url,
            "match_score": job.match_score,
            "jd_excerpt": jd_text[:500],
        }

        violations = self.guard.validate(candidate)
        if self.guard.has_critical_violations(violations):
            safe = copy.deepcopy(base)
            safe = self._reorder_skills(safe, job, jd_text)
            safe["tailored_for"] = candidate["tailored_for"]
            return safe, False, [v.to_dict() for v in violations]

        return candidate, True, [v.to_dict() for v in violations]

    def _build_jd_text(self, job) -> str:
        parts = [
            job.title or "",
            job.company or "",
            job.description or "",
            job.experience or "",
            " ".join(job.skills or []),
            " ".join(job.matched_skills or []),
            " ".join(job.missing_skills or []),
        ]
        return " ".join(p for p in parts if p).lower()

    def _tailor_title(self, resume: dict, job) -> dict:
        jd_title = job.title.lower()
        if "data science" in jd_title:
            resume["title"] = "Data Science Fresher | Data Analyst | Python & ML"
        elif "data engineer" in jd_title:
            resume["title"] = "Data Engineer | Data Analyst | Python & SQL"
        elif "power bi" in jd_title or "bi developer" in jd_title:
            resume["title"] = "Data Analyst | Power BI Developer | DAX & SQL"
        elif "business analyst" in jd_title:
            resume["title"] = "Business Analyst | Data Analyst | Power BI & SQL"
        elif "machine learning" in jd_title or "ml engineer" in jd_title:
            resume["title"] = "ML Engineer Fresher | Data Science | Python"
        elif "data analyst" in jd_title or "analytics" in jd_title:
            resume["title"] = "Data Analyst | Data Science Fresher | Python & Power BI"
        elif "sdet" in jd_title:
            resume["title"] = "SDET | Senior Test Engineer | QA Automation Engineer"
        elif "api" in jd_title and "automation" in jd_title:
            resume["title"] = "QA Automation Engineer | API Testing Specialist"
        elif "manual" in jd_title and ("test" in jd_title or "qa" in jd_title):
            resume["title"] = "Senior Test Engineer | Manual & Automation QA"
        elif "automation" in jd_title:
            resume["title"] = "QA Automation Engineer | Senior Test Engineer"
        elif "lead" in jd_title:
            resume["title"] = "QA Lead | Senior Test Engineer | Automation Engineer"
        elif "senior" in jd_title:
            resume["title"] = "Senior Test Engineer | QA Automation Engineer"
        return resume

    def _tailor_summary(self, resume: dict, job, jd_text: str) -> dict:
        original = resume["summary"]
        company = job.company.strip() or "the organisation"
        role = job.title.strip()

        matched = [s for s in (job.matched_skills or []) if len(s) > 2][:4]
        if matched:
            skills_phrase = ", ".join(matched[:3])
            opener = (
                f"Targeting the {role} role at {company} with proven expertise in "
                f"{skills_phrase}."
            )
        else:
            opener = f"Targeting the {role} role at {company}."

        extras = []
        candidate_text = self._all_text(resume).lower()

        domain_map = {
            "fintech": "open to FinTech domain testing",
            "banking": "applicable experience for financial application testing",
            "e-commerce": "applicable experience for e-commerce platform testing",
            "ecommerce": "applicable experience for e-commerce platform testing",
            "healthcare": "adaptable to healthcare domain testing",
            "saas": "applicable experience for SaaS product testing",
            "telecom": "deep telecom OSS/BSS, billing, and AR testing background",
        }
        for domain, phrase in domain_map.items():
            if domain in jd_text and phrase not in original.lower() and len(extras) < 1:
                extras.append(phrase)

        tool_phrases = {
            "playwright": "hands-on with modern UI automation including Playwright-ready workflows",
            "cucumber": "experienced with structured BDD test design",
            "appium": "open to expanding into mobile automation (Appium)",
            "docker": "familiar with containerized CI/CD environments",
            "python": "comfortable extending automation into Python-based stacks",
            "salesforce": "Salesforce testing exposure in enterprise programmes",
            "sap": "enterprise application testing in complex billing ecosystems",
        }
        for tool, phrase in tool_phrases.items():
            if tool in jd_text and tool in candidate_text and len(extras) < 2:
                extras.append(phrase)
            elif tool in jd_text and tool not in candidate_text and len(extras) < 2:
                open_phrases = {
                    "playwright": "open to Playwright adoption",
                    "cucumber": "open to BDD/Cucumber adoption",
                    "appium": "open to mobile automation (Appium)",
                    "python": "comfortable picking up Python automation",
                }
                if tool in open_phrases:
                    extras.append(open_phrases[tool])

        body = original
        if not body.lower().startswith(opener.lower()[:20]):
            body = f"{opener} {body}"

        if extras:
            body = body.rstrip(".") + ". " + " ".join(s.capitalize() + "." for s in extras)

        resume["summary"] = body
        return resume

    def _reorder_skills(self, resume: dict, job, jd_text: str) -> dict:
        jd_terms = self._jd_terms(jd_text)
        matched_lower = [s.lower() for s in (job.matched_skills or [])]

        for category, skills in resume["skills"].items():
            def score(skill):
                sl = skill.lower()
                s = 0
                if sl in matched_lower:
                    s += 3
                if any(term in sl or sl in term for term in jd_terms):
                    s += 2
                if sl in jd_text:
                    s += 1
                return -s

            resume["skills"][category] = sorted(skills, key=score)

        # Surface categories most relevant to this JD first
        cat_scores = {}
        for cat, skills in resume["skills"].items():
            cat_scores[cat] = sum(
                1 for s in skills[:5]
                if s.lower() in jd_text or s.lower() in matched_lower
            )
        ordered = dict(sorted(resume["skills"].items(), key=lambda x: -cat_scores.get(x[0], 0)))
        resume["skills"] = ordered
        return resume

    def _reorder_experience(self, resume: dict, jd_text: str) -> dict:
        jd_terms = self._jd_terms(jd_text)
        for exp in resume.get("experience", []):
            bullets = exp.get("bullets", [])

            def bullet_score(text):
                tl = text.lower()
                return sum(1 for t in jd_terms if t in tl)

            exp["bullets"] = sorted(bullets, key=bullet_score, reverse=True)
        return resume

    def _reorder_projects(self, resume: dict, jd_text: str) -> dict:
        projects = resume.get("projects", [])
        if not projects:
            return resume

        def proj_score(p):
            text = f"{p.get('name', '')} {p.get('description', '')}".lower()
            score = 0
            if "automation" in jd_text and "automation" in text:
                score += 2
            if "api" in jd_text and "api" in text:
                score += 1
            if "selenium" in jd_text and "selenium" in text:
                score += 2
            return -score

        resume["projects"] = sorted(projects, key=proj_score)
        return resume

    def _jd_terms(self, jd_text: str) -> list:
        found = [t for t in self.JD_SKILL_TERMS if t in jd_text]
        return found

    def get_skill_gap_advice(self, job) -> list:
        advice = []
        jd_text = self._build_jd_text(job)
        candidate_text = self._all_text(self.base_resume).lower()
        learning_map = {
            "cucumber": "Learn BDD/Cucumber — frequently asked",
            "appium": "Pick up Appium basics — mobile QA in demand",
            "docker": "Get hands-on with Docker for CI/CD",
            "playwright": "Learn Playwright — modern Selenium alternative",
            "python": "Add Python automation to your stack",
            "k6": "Try k6/JMeter for performance testing",
            "jmeter": "Try JMeter for load testing",
            "kubernetes": "Awareness of K8s in CI/CD pipelines",
        }
        for tool, msg in learning_map.items():
            if tool in jd_text and tool not in candidate_text:
                advice.append(msg)
        return advice

    @staticmethod
    def _all_text(resume: dict) -> str:
        parts = [resume.get("summary", "")]
        for exp in resume.get("experience", []):
            parts.extend(exp.get("bullets", []))
            parts.append(exp.get("title", ""))
        for cat, items in resume.get("skills", {}).items():
            parts.extend(items)
        return " ".join(parts)
