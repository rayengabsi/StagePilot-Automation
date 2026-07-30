---
version: 1.0.0
purpose: Tailor the candidate's resume sections for a specific job
inputs:
  - profile_json: object
  - job_title: string
  - job_description: string
  - matched_skills: list[string]
  - missing_skills: list[string]
output: JSON object with sections containing rewritten content
---

You are helping a candidate tailor their resume for a specific job application.

Job Title: $job_title
Job Description: $job_description

Skills the employer seeks that the candidate has: $matched_skills
Skills the employer seeks that the candidate lacks: $missing_skills

Below is the candidate's full profile. Rewrite the following resume sections to emphasize the matching skills and experience relevant to this job.

Candidate Profile:
$profile_json

Return a JSON object with these keys:
- "summary": A 2-3 sentence professional summary highlighting the best match for this job
- "skills": A reordered skills section with matched skills first
- "experience": Bullet points rewritten to emphasize relevant experience (max 5 bullets)
- "projects": Relevant project highlights (max 3)

IMPORTANT RULES:
- Do NOT invent degrees, jobs, skills, certifications, projects, or dates
- All content must originate from the profile provided
- Reorder and rephrase only
- Return ONLY valid JSON
