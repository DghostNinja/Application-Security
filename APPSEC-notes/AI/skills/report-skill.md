---
name: vulnerability-report-writer
description: Generates professional penetration testing findings from a brief vulnerability description.
---

# Vulnerability Report Writer

## Purpose

Convert a short vulnerability description into a concise, professional penetration testing finding.

## Output Format

Produce the following sections in this exact order:

## Title

Provide a short, professional vulnerability name.

Examples:

- Authentication Bypass on BOC Update Table Status Endpoint
- Missing Server-Side Authorization on User Management API
- Insecure Direct Object Reference (IDOR) in Order API
- Stored Cross-Site Scripting in Support Tickets
- SQL Injection in Search Functionality

---

## Severity

Choose one of:

- Critical
- High
- Medium
- Low
- Informational

Base the severity on the demonstrated impact only. Do not exaggerate.

General guidance:

- Critical – Remote compromise, authentication bypass leading to full application compromise, RCE, unrestricted administrative access, or large-scale sensitive data exposure.
- High – Privilege escalation, IDOR exposing sensitive data, significant authentication or authorization flaws, SQL injection, stored XSS affecting privileged users.
- Medium – Reflected XSS, CSRF, information disclosure with limited impact, weak access controls with constrained impact, security misconfigurations.
- Low – Missing security headers, verbose error messages, weak cookie attributes, rate limiting issues with limited impact.
- Informational – Best practice observations with no direct security impact.

---

## Description

Describe:

- What the vulnerability is.
- Why it exists.
- What submitting crafted input can achieve.
- The resulting security impact.

Write as a single paragraph.

Example style:

The BOC Update Table Status endpoint does not enforce proper authentication and remains accessible even after all session cookies and JWTs have been removed. This allows unauthenticated users to access functionality intended for authenticated users, potentially resulting in unauthorized access or modification of application data.

---

## Recommendation

Describe how the issue should be remediated.

Focus on server-side controls.

Example style:

It is recommended to require authentication for all requests to the BOC Update Table Status endpoint and implement server-side authorization checks to ensure only authorized users can access or interact with the resource. Additionally, avoid relying solely on client-side controls to enforce access restrictions.

---

# Writing Rules

- Maintain a professional penetration testing tone.
- Never exaggerate impact.
- Never speculate beyond the provided evidence.
- Do not mention the tester.
- Do not use the term "attacker". Describe the effect directly.
- Do not mention proof-of-concept steps.
- Use present tense.
- Do not use bullet points inside Description or Recommendation.
- Keep Description to approximately 75–150 words.
- Keep Recommendation to approximately 40–100 words.

---

# Vulnerability Guidance

Authentication Bypass
- Mention missing authentication enforcement.
- Recommend enforcing authentication on the server.

Authorization / IDOR
- Mention missing server-side authorization.
- Recommend object-level authorization checks.

Privilege Escalation
- Mention insufficient privilege validation.
- Recommend role-based authorization checks.

SQL Injection
- Mention parameterized queries and input validation.

Cross-Site Scripting
- Mention output encoding and input validation.
- Recommend Content Security Policy where appropriate.

CSRF
- Mention CSRF tokens and SameSite cookies.

Sensitive Information Disclosure
- Recommend least privilege, data minimization, and restricting exposed fields.

Security Misconfiguration
- Recommend secure default configurations and removing unnecessary exposure.

Rate Limiting
- Recommend server-side throttling and account protections.

---

# Example

## Input

The Update Table Status endpoint is still accessible after deleting the JWT and session cookies.

## Output

### Title

Authentication Bypass on BOC Update Table Status Endpoint

### Severity

High

### Description

The BOC Update Table Status endpoint does not enforce proper authentication and remains accessible even after all session cookies and JWTs have been removed. This allows unauthenticated users to access functionality intended for authenticated users, potentially resulting in unauthorized access or modification of application data.

### Recommendation

It is recommended to require authentication for all requests to the BOC Update Table Status endpoint and implement server-side authorization checks to ensure only authorized users can access or interact with the resource. Additionally, avoid relying solely on client-side controls to enforce access restrictions.
