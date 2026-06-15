"""
JD Analyzer — scores each job against your skill profile.
No external API needed — pure keyword matching with smart weighting.
"""
import re
from scraper.base_scraper import Job


class JDScorer:

    def __init__(self, config: dict):
        self.primary_skills = [s.lower() for s in config["your_skills"]["primary"]]
        self.secondary_skills = [s.lower() for s in config["your_skills"]["secondary"]]
        self.domain_skills = [s.lower() for s in config["your_skills"]["domain"]]
        self.preferred_locations = [l.lower() for l in config["search"]["locations"]]
        self.search_keywords = [k.lower() for k in config["search"]["keywords"]]
        self.weights = config["scoring"]
        self.role_terms = [
            "qa", "sdet", "test engineer", "automation", "selenium",
            "quality assurance", "software test", "manual test", "manual testing",
            "manual qa", "api test", "quality analyst",
        ]

    def score(self, job: Job) -> Job:
        """Score a job and attach match details to it."""
        text = self._get_text(job)

        primary_matched, primary_score = self._match_skills(text, self.primary_skills)
        secondary_matched, secondary_score = self._match_skills(text, self.secondary_skills)
        role_score, role_matched = self._score_role_relevance(job.title)
        exp_score = self._score_experience(text)
        loc_score = self._score_location(job.location)

        # LinkedIn guest API returns title-only cards — lean on role + location signals
        has_description = bool(job.description.strip())
        if not has_description:
            primary_score = max(primary_score, role_score)

        # Weighted total score
        total = (
            primary_score * self.weights["primary_skill_match"] / 100 +
            secondary_score * self.weights["secondary_skill_match"] / 100 +
            exp_score * self.weights["experience_match"] / 100 +
            loc_score * self.weights["location_match"] / 100
        )
        if not has_description and role_score:
            total += role_score * self.weights.get("role_relevance", 10) / 100

        job.match_score = round(min(total, 100))
        job.matched_skills = primary_matched + secondary_matched + role_matched
        job.missing_skills = [
            s for s in self.primary_skills if s not in [m.lower() for m in primary_matched]
        ]
        return job

    def _get_text(self, job: Job) -> str:
        return f"{job.title} {job.description} {' '.join(job.skills)}".lower()

    def _score_role_relevance(self, title: str) -> tuple:
        """Score how well the job title matches QA/SDET roles (works without JD text)."""
        title_lower = title.lower()
        matched = []
        for kw in self.search_keywords:
            if kw.lower() in title_lower:
                matched.append(kw)
        for term in self.role_terms:
            if term in title_lower and term not in [m.lower() for m in matched]:
                matched.append(term.title())
        if not matched:
            return 0, []
        # 1 match = 60%, 2+ = 85%, 3+ = 100%
        score = 60 if len(matched) == 1 else (85 if len(matched) == 2 else 100)
        return score, matched[:5]

    def _match_skills(self, text: str, skill_list: list) -> tuple:
        matched = []
        for skill in skill_list:
            # Handle multi-word skills and common abbreviations
            pattern = re.escape(skill.lower())
            if re.search(pattern, text):
                matched.append(skill.title())
        score = (len(matched) / len(skill_list)) * 100 if skill_list else 0
        return matched, score

    def _score_experience(self, text: str) -> float:
        """Check if job experience range matches 3-6 years."""
        patterns = [
            r"(\d+)\s*[-–to]+\s*(\d+)\s*years?",
            r"(\d+)\+?\s*years?\s*(?:of)?\s*experience",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 2:
                        min_exp = int(groups[0])
                        max_exp = int(groups[1])
                        if min_exp <= 6 and max_exp >= 3:
                            return 100
                        elif min_exp <= 7:
                            return 70
                    else:
                        exp = int(groups[0])
                        if 3 <= exp <= 7:
                            return 100
                        elif exp <= 8:
                            return 60
                except Exception:
                    pass
        return 50  # neutral if not found

    def _score_location(self, location: str) -> float:
        location_lower = location.lower()
        for pref in self.preferred_locations:
            if pref in location_lower:
                return 100
        if "remote" in location_lower or "work from home" in location_lower:
            return 100
        if "india" in location_lower:
            return 60
        return 20

    def score_all(self, jobs: list) -> list:
        """Score all jobs and return sorted by match score (highest first)."""
        scored = [self.score(job) for job in jobs]
        scored.sort(key=lambda j: j.match_score, reverse=True)
        return scored

    def filter_by_min_score(self, jobs: list, min_score: int) -> list:
        return [j for j in jobs if j.match_score >= min_score]
