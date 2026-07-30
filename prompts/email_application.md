---
version: 1.0.0
purpose: Draft a professional application email
inputs:
  - recipient_name: string
  - company: string
  - job_title: string
  - cover_letter_body: string
  - candidate_name: string
output: JSON with subject, body, and signature
---

Draft a professional job application email.

Recipient: $recipient
Company: $company
Job Title: $job_title
Candidate Name: $candidate_name

Cover Letter to include:
$cover_letter_body

Return a JSON object with these keys:
- "subject": A clear, professional subject line mentioning the job title
- "body": The email body incorporating the cover letter content, formatted as plain text (not markdown), with paragraph breaks
- "signature": A professional email signature with the candidate's name

IMPORTANT:
- Do NOT invent contact information (phone, email, address)
- Use generic placeholders like [phone] or [email] if not provided
- Return ONLY valid JSON
