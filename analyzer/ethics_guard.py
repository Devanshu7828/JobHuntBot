"""
EthicsGuard — the anti-lying validator.

Ensures any tailored resume does NOT contain fabricated content:
- No skills the candidate doesn't actually have
- No inflated years of experience
- No new companies / projects / certifications
- No false claims of certifications
- No invented metrics (e.g. "increased X by 300%")

This module is intentionally strict. Any violation rejects the tailored
version and falls back to the safe base resume.
"""
import re
from typing import List


class EthicsViolation:
    def __init__(self, severity: str, rule: str, detail: str):
        self.severity = severity   # CRITICAL | HIGH | MEDIUM
        self.rule = rule
        self.detail = detail

    def __repr__(self):
        return f"[{self.severity}] {self.rule}: {self.detail}"

    def to_dict(self):
        return {"severity": self.severity, "rule": self.rule, "detail": self.detail}


class EthicsGuard:
    """Validates that tailored resume content is truthful vs base resume."""

    # Buzz claims that look impressive but are usually fabricated
    SUSPICIOUS_CLAIMS = [
        r"increased\s+\w+\s+by\s+\d{2,}%",
        r"reduced\s+\w+\s+by\s+\d{2,}%",
        r"saved\s+\$\d+",
        r"led\s+team\s+of\s+\d{2,}",       # "led team of 50+"
        r"\d{4,}\+?\s+test\s+cases",        # "10,000+ test cases"
        r"reduced\s+bug.+by\s+\d+%",
    ]

    def __init__(self, base_resume: dict):
        self.base = base_resume
        self.base_skills_lower = self._collect_all_skills(base_resume)
        self.base_companies = self._collect_companies(base_resume)
        self.base_certs_lower = [c.lower() for c in base_resume.get("certifications", [])]

    def _collect_all_skills(self, resume: dict) -> set:
        skills = set()
        skill_dict = resume.get("skills", {})
        for category, items in skill_dict.items():
            for skill in items:
                skills.add(skill.lower().strip())
        return skills

    def _collect_companies(self, resume: dict) -> set:
        return {exp.get("company", "").lower().strip()
                for exp in resume.get("experience", [])}

    def _count_experience_years(self, resume: dict) -> int:
        """Sum total years of experience from resume."""
        total_months = 0
        for exp in resume.get("experience", []):
            duration = exp.get("duration", "")
            # Match patterns like "Jul 2021 – Present" or "Aug 2021 – Oct 2023"
            years = re.findall(r"(\d{4})", duration)
            if len(years) >= 2:
                start, end = int(years[0]), int(years[1])
                total_months += (end - start) * 12
            elif "present" in duration.lower():
                if years:
                    start = int(years[0])
                    total_months += (2026 - start) * 12  # current year
        return total_months // 12

    def validate(self, tailored: dict) -> List[EthicsViolation]:
        """Run all checks. Returns empty list if clean."""
        violations = []
        violations.extend(self._check_skills(tailored))
        violations.extend(self._check_companies(tailored))
        violations.extend(self._check_certifications(tailored))
        violations.extend(self._check_experience_inflation(tailored))
        violations.extend(self._check_suspicious_claims(tailored))
        return violations

    def _check_skills(self, tailored: dict) -> List[EthicsViolation]:
        violations = []
        tailored_skills = self._collect_all_skills(tailored)
        fabricated = tailored_skills - self.base_skills_lower
        for skill in fabricated:
            violations.append(EthicsViolation(
                "CRITICAL", "FABRICATED_SKILL",
                f"Skill '{skill}' is not in base resume"
            ))
        return violations

    def _check_companies(self, tailored: dict) -> List[EthicsViolation]:
        violations = []
        tailored_companies = self._collect_companies(tailored)
        new_companies = tailored_companies - self.base_companies
        for company in new_companies:
            if company:
                violations.append(EthicsViolation(
                    "CRITICAL", "FABRICATED_COMPANY",
                    f"Company '{company}' not in base resume"
                ))
        return violations

    def _check_certifications(self, tailored: dict) -> List[EthicsViolation]:
        violations = []
        tailored_certs = [c.lower() for c in tailored.get("certifications", [])]
        for cert in tailored_certs:
            if cert not in self.base_certs_lower:
                # Allow minor reformatting — check substring overlap
                matches = [bc for bc in self.base_certs_lower
                           if self._fuzzy_match(cert, bc)]
                if not matches:
                    violations.append(EthicsViolation(
                        "HIGH", "FABRICATED_CERT",
                        f"Certification '{cert}' not in base resume"
                    ))
        return violations

    def _check_experience_inflation(self, tailored: dict) -> List[EthicsViolation]:
        violations = []
        base_years = self._count_experience_years(self.base)
        tailored_years = self._count_experience_years(tailored)
        if tailored_years > base_years + 1:   # allow 1-year rounding tolerance
            violations.append(EthicsViolation(
                "CRITICAL", "EXPERIENCE_INFLATED",
                f"Tailored shows {tailored_years} yrs vs base {base_years} yrs"
            ))
        return violations

    def _check_suspicious_claims(self, tailored: dict) -> List[EthicsViolation]:
        """Check for claims that don't appear in base resume."""
        violations = []
        base_text = self._extract_all_text(self.base).lower()
        for exp in tailored.get("experience", []):
            for bullet in exp.get("bullets", []):
                bullet_lower = bullet.lower()
                # If bullet contains a suspicious pattern AND that pattern
                # doesn't appear in base resume, flag it.
                for pattern in self.SUSPICIOUS_CLAIMS:
                    match = re.search(pattern, bullet_lower)
                    if match and match.group() not in base_text:
                        violations.append(EthicsViolation(
                            "MEDIUM", "FABRICATED_METRIC",
                            f"Unverified claim: '{match.group()}'"
                        ))
        return violations

    def _extract_all_text(self, resume: dict) -> str:
        parts = [resume.get("summary", "")]
        for exp in resume.get("experience", []):
            parts.extend(exp.get("bullets", []))
        for proj in resume.get("projects", []):
            parts.append(proj.get("description", ""))
        return " ".join(parts)

    def _fuzzy_match(self, a: str, b: str, threshold: float = 0.6) -> bool:
        """Simple substring overlap. Replace with rapidfuzz for production."""
        a, b = a.lower(), b.lower()
        if a in b or b in a:
            return True
        # Token overlap
        a_tokens = set(a.split())
        b_tokens = set(b.split())
        if not a_tokens or not b_tokens:
            return False
        overlap = len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))
        return overlap >= threshold

    def has_critical_violations(self, violations: List[EthicsViolation]) -> bool:
        return any(v.severity == "CRITICAL" for v in violations)
