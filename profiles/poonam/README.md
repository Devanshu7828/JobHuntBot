# Poonam Rajak — Data Analyst / Data Science Profile

## Quick start

```powershell
cd JobHuntBot
py -m pip install -r requirements.txt
py -m playwright install chromium
py main.py --config profiles/poonam/config.yaml
```

Or double-click: `profiles/poonam/run.bat`

## What is configured

| Setting | Value |
|---------|--------|
| Roles | Data Analyst, Data Science, Business Analyst, Power BI, etc. |
| Experience | 0–2 years (fresher / entry-level) |
| Salary | 3–12 LPA |
| Locations | Pune, Gurgaon, Remote, Bengaluru, Indore |
| Outputs | `output/poonam/jobs/` and `output/poonam/resumes/` |

## On her laptop — update only if needed

1. **`profiles/poonam/config.yaml`** — if her master PDF is elsewhere, change:
   ```yaml
   resume:
     master_resume_pdf: "C:/Users/HerName/Documents/PoonamRajak_Data_Analyst_Resume_2026.pdf"
   ```
2. Keep **`profiles/poonam/base_resume.json`** in sync when she updates her resume.

## Your profile (Devanshu) — unchanged

```powershell
py main.py
# uses config.yaml in project root
```
