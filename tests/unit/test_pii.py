from __future__ import annotations

from app.utils import pii


def test_mask_email_typical() -> None:
    assert pii.mask_email("rayen@example.com") == "r***n@example.com"


def test_mask_email_short_local() -> None:
    assert pii.mask_email("ab@test.com") == "a***@test.com"


def test_mask_email_single_char() -> None:
    assert pii.mask_email("a@b.co") == "a***@b.co"


def test_mask_email_none() -> None:
    assert pii.mask_email(None) is None


def test_mask_email_empty() -> None:
    assert pii.mask_email("") is None


def test_mask_email_invalid_format() -> None:
    assert pii.mask_email("not-an-email") == "not-an-email"


def test_mask_phone_typical() -> None:
    masked = pii.mask_phone("+21653852323")
    assert masked is not None
    assert masked.startswith("+21653")
    assert masked == "+21653******"


def test_mask_phone_short() -> None:
    assert pii.mask_phone("123") == "123"


def test_mask_phone_none() -> None:
    assert pii.mask_phone(None) is None


def test_mask_phone_empty() -> None:
    assert pii.mask_phone("") is None


def test_mask_url_typical() -> None:
    masked = pii.mask_url("https://github.com/johndoe")
    assert masked is not None
    assert masked.startswith("https://")
    assert "github" in masked or "***" in masked


def test_mask_url_none() -> None:
    assert pii.mask_url(None) is None


def test_mask_url_empty() -> None:
    assert pii.mask_url("") is None


def test_mask_url_no_protocol() -> None:
    assert pii.mask_url("not-a-url") == "not-a-url"


def test_mask_linkedin() -> None:
    masked = pii.mask_linkedin("https://linkedin.com/in/rayen")
    assert masked is not None
    assert masked.startswith("https://")
    assert "***" in masked


def test_mask_github() -> None:
    masked = pii.mask_github("https://github.com/rayenmehri")
    assert masked is not None
    assert masked.startswith("https://")


def test_mask_portfolio() -> None:
    masked = pii.mask_portfolio("https://rayen.dev")
    assert masked is not None
    assert "***" in masked


def test_mask_value_by_key() -> None:
    assert pii.mask_value("email", "test@example.com") is not None
    assert pii.mask_value("phone", "+21653852323") is not None
    assert pii.mask_value("linkedin_url", "https://linkedin.com/in/x") is not None
    assert pii.mask_value("github_url", "https://github.com/x") is not None
    assert pii.mask_value("portfolio_url", "https://x.dev") is not None
    assert pii.mask_value("full_name", "John Doe") == "John Doe"


def test_mask_value_none() -> None:
    assert pii.mask_value("email", None) is None


def test_mask_value_empty() -> None:
    assert pii.mask_value("email", "") is None


def test_mask_profile_dict() -> None:
    data = {
        "email": "rayen@example.com",
        "phone": "+21653852323",
        "linkedin_url": "https://linkedin.com/in/rayen",
        "github_url": "https://github.com/rayen",
        "portfolio_url": "https://rayen.dev",
        "full_name": "Rayen Mehri",
    }
    masked = pii.mask_profile_dict(data)
    assert masked["email"] != "rayen@example.com"
    assert "***" in masked["email"]
    assert masked["full_name"] == "Rayen Mehri"
    assert "***" in masked["phone"]
    assert "***" in masked["linkedin_url"]
    assert masked.keys() == data.keys()


def test_mask_profile_dict_empty() -> None:
    assert pii.mask_profile_dict({}) == {}


def test_mask_profile_dict_no_pii() -> None:
    data = {"name": "John", "age": 30}
    assert pii.mask_profile_dict(data) == data
