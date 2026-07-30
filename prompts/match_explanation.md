---
version: 1.0.0
purpose: Generate a natural-language explanation of why a job matches the candidate
inputs:
  - job_title: string
  - company: string
  - final_score: float
  - matched_skills: list[string]
  - missing_skills: list[string]
  - matched_technologies: list[string]
  - missing_technologies: list[string]
  - score_breakdown: dict
  - hard_rule_result: dict
output: A concise natural-language paragraph (2-4 sentences)
---

Write a natural-language paragraph explaining why this job is a good match for the candidate.

Job: $job_title at $company
Overall Match Score: $final_score/100

Skills the candidate has that match: $matched_skills
Skills the candidate is missing: $missing_skills

Technologies the candidate has that match: $matched_technologies
Technologies the candidate is missing: $missing_technologies

Score breakdown by category: $score_breakdown

Hard rule check: $hard_rule_result

Write a concise, professional explanation (2-4 sentences). Start with a summary of whether this is a good match. Mention the strongest matching areas and the most notable gaps. Do NOT invent any skills or experience not listed above.
