---
version: 1.0.0
purpose: Generate a personalized cover letter for a job application
inputs:
  - candidate_name: string
  - job_title: string
  - company: string
  - matched_skills: list[string]
  - education: list[object]
  - experience: list[object]
output: A professional cover letter body (3-4 paragraphs)
---

Write a personalized cover letter for the following job application.

Candidate Name: $candidate_name
Job Title: $job_title
Company: $company
Recipient: $recipient

Matching Skills: $matched_skills

Education:
$education

Experience:
$experience

Write a professional cover letter (3-4 paragraphs) that:
1. Expresses interest in the position at $company
2. Highlights the candidate's most relevant skills and experience
3. Mentions specific education that is relevant
4. Closes with enthusiasm and a call to action

IMPORTANT RULES:
- Do NOT invent degrees, jobs, skills, certifications, or dates
- All claims must be verifiable from the information provided
- Keep it concise and professional
