"""
Generates a rich, interactive HTML report of all job matches.
Shows match score, matched/missing skills, tailored PDFs, and direct apply links.
"""
import os
from datetime import date


def generate_report(jobs: list, output_path: str, candidate_name: str, master_resume_pdf: str = ""):
    """Generate HTML job report and save to output_path."""
    today = date.today().strftime("%d %b %Y")
    total = len(jobs)
    high_match = len([j for j in jobs if j.match_score >= 75])
    good_match = len([j for j in jobs if 50 <= j.match_score < 75])
    low_match = len([j for j in jobs if j.match_score < 50])

    platform_counts = {}
    for job in jobs:
        platform_counts[job.platform] = platform_counts.get(job.platform, 0) + 1

    platform_stat_cards = "".join(
        f'<div class="stat-card"><div class="num blue">{v}</div><div class="label">{k}</div></div>'
        for k, v in platform_counts.items()
    )
    platform_filter_buttons = "".join(
        f'<button class="filter-btn" onclick="filterPlatform(\'{k}\')">{k} ({v})</button>'
        for k, v in platform_counts.items()
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Hunt Report — {today}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; color: #1a1a2e; }}
  .header {{ background: linear-gradient(135deg, #1a3c6e, #16213e); color: white; padding: 32px 40px; }}
  .header h1 {{ font-size: 26px; font-weight: 700; }}
  .header p {{ opacity: 0.8; margin-top: 6px; }}
  .stats {{ display: flex; gap: 16px; padding: 24px 40px; flex-wrap: wrap; }}
  .stat-card {{ background: white; border-radius: 10px; padding: 20px 28px; flex: 1; min-width: 140px;
               box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }}
  .stat-card .num {{ font-size: 32px; font-weight: 700; }}
  .stat-card .label {{ font-size: 12px; color: #666; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .green {{ color: #2e7d32; }} .orange {{ color: #e65100; }} .red {{ color: #c62828; }} .blue {{ color: #1565c0; }}
  .filters {{ padding: 0 40px 16px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
  .filter-btn {{ padding: 8px 18px; border-radius: 20px; border: 2px solid #1a3c6e; background: white;
                 color: #1a3c6e; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s; }}
  .filter-btn:hover, .filter-btn.active {{ background: #1a3c6e; color: white; }}
  .jobs {{ padding: 0 40px 40px; display: grid; gap: 16px; }}
  .job-card {{ background: white; border-radius: 12px; padding: 22px 26px; box-shadow: 0 2px 8px rgba(0,0,0,0.07);
               border-left: 5px solid #ccc; transition: transform 0.15s, box-shadow 0.15s; }}
  .job-card:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.12); }}
  .job-card.high {{ border-left-color: #2e7d32; }}
  .job-card.good {{ border-left-color: #e65100; }}
  .job-card.low  {{ border-left-color: #9e9e9e; }}
  .job-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }}
  .job-title {{ font-size: 17px; font-weight: 700; color: #1a3c6e; }}
  .company {{ font-size: 14px; color: #444; margin-top: 4px; }}
  .meta {{ font-size: 12px; color: #888; margin-top: 6px; display: flex; gap: 16px; flex-wrap: wrap; }}
  .score-badge {{ padding: 8px 16px; border-radius: 20px; font-weight: 700; font-size: 15px;
                  white-space: nowrap; min-width: 60px; text-align: center; }}
  .score-high {{ background: #e8f5e9; color: #2e7d32; }}
  .score-good {{ background: #fff3e0; color: #e65100; }}
  .score-low  {{ background: #f5f5f5; color: #757575; }}
  .skills-section {{ margin-top: 14px; display: flex; gap: 20px; flex-wrap: wrap; }}
  .skills-group {{ flex: 1; min-width: 200px; }}
  .skills-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
                   color: #888; margin-bottom: 6px; }}
  .skill-tag {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px;
                margin: 2px; font-weight: 500; }}
  .tag-match {{ background: #e8f5e9; color: #2e7d32; }}
  .tag-missing {{ background: #fce4ec; color: #c62828; }}
  .actions {{ margin-top: 16px; display: flex; gap: 10px; flex-wrap: wrap; }}
  .btn {{ padding: 9px 20px; border-radius: 8px; font-size: 13px; font-weight: 600;
          cursor: pointer; text-decoration: none; border: none; display: inline-block; }}
  .btn-primary {{ background: #1a3c6e; color: white; }}
  .btn-primary:hover {{ background: #1565c0; }}
  .btn-secondary {{ background: white; color: #1a3c6e; border: 2px solid #1a3c6e; }}
  .btn-secondary:hover {{ background: #e3f2fd; }}
  .platform-badge {{ padding: 3px 10px; border-radius: 10px; font-size: 11px; font-weight: 700;
                     background: #e3f2fd; color: #1565c0; }}
  .salary {{ color: #2e7d32; font-weight: 600; }}
  .no-jobs {{ text-align: center; padding: 60px; color: #888; font-size: 16px; }}
</style>
</head>
<body>

<div class="header">
  <h1>🎯 Job Hunt Report — {today}</h1>
  <p>{candidate_name} &nbsp;|&nbsp; QA Automation Engineer &nbsp;|&nbsp; Pune / Remote / Pan-India</p>
</div>

<div class="stats">
  <div class="stat-card"><div class="num blue">{total}</div><div class="label">Total Jobs Found</div></div>
  <div class="stat-card"><div class="num green">{high_match}</div><div class="label">High Match (75%+)</div></div>
  <div class="stat-card"><div class="num orange">{good_match}</div><div class="label">Good Match (50-74%)</div></div>
  <div class="stat-card"><div class="num red">{low_match}</div><div class="label">Low Match (&lt;50%)</div></div>
  {platform_stat_cards}
</div>

<div class="filters">
  <strong style="font-size:13px;">Filter:</strong>
  <button class="filter-btn active" onclick="filterJobs('all')">All ({total})</button>
  <button class="filter-btn" onclick="filterJobs('high')">🟢 High Match ({high_match})</button>
  <button class="filter-btn" onclick="filterJobs('good')">🟡 Good Match ({good_match})</button>
  {platform_filter_buttons}
</div>

<div class="jobs" id="jobList">
"""

    if not jobs:
        html += '<div class="no-jobs">No jobs found matching your criteria. Try adjusting keywords in config.yaml</div>'
    else:
        for i, job in enumerate(jobs):
            score_class = "high" if job.match_score >= 75 else ("good" if job.match_score >= 50 else "low")
            badge_class = "score-high" if job.match_score >= 75 else ("score-good" if job.match_score >= 50 else "score-low")

            matched_tags = "".join([f'<span class="skill-tag tag-match">{s}</span>' for s in job.matched_skills[:10]])
            missing_tags = "".join([f'<span class="skill-tag tag-missing">{s}</span>' for s in job.missing_skills[:6]])

            resume_btn = ""
            tailored_path = getattr(job, "tailored_resume_path", "") or ""
            if tailored_path and os.path.isfile(tailored_path):
                resume_url = "file:///" + os.path.abspath(tailored_path).replace("\\", "/")
                resume_btn = (
                    f'<a href="{resume_url}" target="_blank" class="btn btn-secondary">'
                    f'📄 Tailored Resume</a>'
                )

            master_btn = ""
            master_path = getattr(job, "master_resume_path", "") or master_resume_pdf
            if master_path and os.path.isfile(master_path):
                master_url = "file:///" + os.path.abspath(master_path).replace("\\", "/")
                master_btn = (
                    f'<a href="{master_url}" target="_blank" class="btn btn-secondary">'
                    f'📋 Master Resume</a>'
                )

            cover_btn = ""
            cover_path = getattr(job, "cover_letter_path", "") or ""
            if cover_path:
                cover_url = "file:///" + os.path.abspath(cover_path).replace("\\", "/")
                cover_btn = f'<a href="{cover_url}" target="_blank" class="btn btn-secondary">📝 Cover Letter</a>'

            ethics_warning = ""
            if getattr(job, "ethics_passed", True) is False:
                ethics_warning = '<span style="color:#c62828;font-size:11px;font-weight:600;margin-left:8px;">⚠ Ethics check rolled back to safe resume</span>'

            missing_section = ""
            if missing_tags:
                missing_section = "<div class='skills-group'><div class='skills-label'>❌ Skills to Highlight / Learn</div>" + missing_tags + "</div>"

            html += f"""
  <div class="job-card {score_class}" data-score="{score_class}" data-platform="{job.platform}" id="job-{i}">
    <div class="job-top">
      <div>
        <div class="job-title">{job.title}</div>
        <div class="company">🏢 {job.company}</div>
        <div class="meta">
          <span>📍 {job.location}</span>
          <span class="salary">💰 {job.salary}</span>
          <span>🗓️ {job.posted_date}</span>
          <span><span class="platform-badge">{job.platform}</span></span>
          <span>⏱️ {job.experience}</span>
        </div>
      </div>
      <div class="{badge_class} score-badge">{job.match_score}%</div>
    </div>

    <div class="skills-section">
      <div class="skills-group">
        <div class="skills-label">✅ Your Matching Skills</div>
        {matched_tags if matched_tags else '<span style="color:#999;font-size:12px;">Run with description fetch for detailed match</span>'}
      </div>
      {missing_section}
    </div>

    <div class="actions">
      <a href="{job.url}" target="_blank" class="btn btn-primary">🔗 Apply Now</a>
      {resume_btn}
      {master_btn}
      {cover_btn}
      <button class="btn btn-secondary" onclick="copyJob({i})">📋 Copy JD Info</button>
      {ethics_warning}
    </div>
  </div>
"""

    html += f"""
</div>

<script>
  const jobs = {[{"id": i, "title": j.title, "company": j.company, "url": j.url, "platform": j.platform, "score": j.match_score, "matched": j.matched_skills, "missing": j.missing_skills} for i, j in enumerate(jobs)]};

  function filterJobs(type) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.job-card').forEach(card => {{
      if (type === 'all') {{ card.style.display = ''; }}
      else {{ card.style.display = card.dataset.score === type ? '' : 'none'; }}
    }});
  }}

  function filterPlatform(platform) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.job-card').forEach(card => {{
      card.style.display = card.dataset.platform === platform ? '' : 'none';
    }});
  }}

  function copyJob(id) {{
    const job = jobs[id];
    const text = `Job: ${{job.title}}\\nCompany: ${{job.company}}\\nPlatform: ${{job.platform}}\\nURL: ${{job.url}}\\nMatch Score: ${{job.score}}%\\nMatched Skills: ${{job.matched.join(', ')}}`;
    navigator.clipboard.writeText(text).then(() => alert('Job info copied to clipboard!'));
  }}
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report saved: {output_path}")
    return output_path
