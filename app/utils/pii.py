"""Reusable helpers for masking personally identifiable information (PII).

All functions return ``None`` when given ``None`` or empty input,
and never modify the original data.
"""

from __future__ import annotations

import re


def mask_email(email: str | None) -> str | None:
    """Mask the local part of an email address, preserving the domain."""
    if not email:
        return None
    match = re.match(r"^(.+)@(.+\..+)$", email)
    if not match:
        return email
    local, domain = match.group(1), match.group(2)
    masked_local = local[0] + "***" if len(local) <= 2 else local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


def mask_phone(phone: str | None) -> str | None:
    """Mask all but the first few digits of a phone number."""
    if not phone:
        return None
    prefix = ""
    rest = phone
    if rest.startswith("+"):
        prefix = "+"
        rest = rest[1:]
    digits = re.sub(r"\D", "", rest)
    if len(digits) < 4:
        return phone
    prefix_len = min(5, len(digits) - 3)
    visible = digits[:prefix_len]
    return prefix + visible.ljust(len(digits), "*")


def mask_url(url: str | None, keep_protocol: bool = True) -> str | None:
    """Mask all but the first and last character of the hostname in a URL."""
    if not url:
        return None
    match = re.match(r"^(https?://)(.+)$", url)
    if not match:
        return url
    protocol, rest = match.group(1), match.group(2)
    host = rest.split("/")[0] if "/" in rest else rest
    masked_host = host[0] + "***" + host[-1] if len(host) > 2 else host + "***"
    return (protocol if keep_protocol else "") + masked_host


def mask_linkedin(url: str | None) -> str | None:
    """Mask a LinkedIn URL."""
    return mask_url(url)


def mask_github(url: str | None) -> str | None:
    """Mask a GitHub URL."""
    return mask_url(url)


def mask_portfolio(url: str | None) -> str | None:
    """Mask a portfolio URL."""
    return mask_url(url)


def mask_value(key: str, value: str | None) -> str | None:
    """Mask a value based on its key name (email/phone/url)."""
    if not value:
        return None
    key_lower = key.lower()
    if "email" in key_lower:
        return mask_email(value)
    if "phone" in key_lower:
        return mask_phone(value)
    if "linkedin" in key_lower:
        return mask_linkedin(value)
    if "github" in key_lower:
        return mask_github(value)
    if "portfolio" in key_lower or "url" in key_lower:
        return mask_url(value)
    return value


def mask_profile_dict(data: dict) -> dict:
    """Return a copy of *data* with known PII fields masked."""
    sensitive_keys = {
        "email",
        "phone",
        "linkedin_url",
        "github_url",
        "portfolio_url",
    }
    result = dict(data)
    for key in sensitive_keys:
        if key in result:
            result[key] = mask_value(key, result[key])
    return result
