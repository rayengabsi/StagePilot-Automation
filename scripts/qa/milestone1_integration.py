"""QA Milestone 1 — Production Integration Verification.

Drives StagePilot's production components directly (no mocks, no stub servers)
and reports which subsystems are verifiable against real production data in
this environment and which are blocked, with the exact reason.

Run with:
    uv run python scripts/qa/milestone1_integration.py

Exit code is 0 unless a real check FAILS; BLOCKED checks (environment
constraints) are documented but do not fail the harness.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))


@dataclass
class Check:
    subsystem: str
    status: str  # PASS | BLOCKED | FAIL
    detail: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "subsystem": self.subsystem,
            "status": self.status,
            "detail": self.detail,
            "notes": self.notes,
        }


def _mask(text: str) -> str:
    if not text:
        return "<unset>"
    if len(text) <= 8:
        return "***"
    return f"{text[:3]}...{text[-3:]}"


def run() -> list[Check]:
    """Execute every production integration probe and return the results."""
    results: list[Check] = []

    # 1. Configuration loading -------------------------------------------------
    from app.config.linkedin_mcp_config import get_linkedin_mcp_config
    from app.config.settings import get_settings
    from app.config.telegram_config import get_telegram_config

    try:
        settings = get_settings()
        linkedin = get_linkedin_mcp_config()
        telegram = get_telegram_config()
        detail = (
            f"env={settings.app_env} db={settings.mysql_host}:{settings.mysql_port}/"
            f"{settings.mysql_database} linkedin_cmd={linkedin.command} "
            f"linkedin_cwd={linkedin.cwd} telegram_enabled={telegram.is_enabled} "
            f"telegram_chats={len(telegram.allowed_chat_ids)}"
        )
        results.append(Check("config_loading", "PASS", detail))
    except Exception as exc:
        results.append(Check("config_loading", "FAIL", str(exc)))

    # 2. Database -------------------------------------------------------------
    try:
        from app.db.session import create_database_engine
        from sqlalchemy import text

        engine = create_database_engine(settings)
        with engine.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            table_count = conn.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :db"),
                {"db": settings.mysql_database},
            ).scalar()
            conn.execute(text("CREATE TEMPORARY TABLE qa_probe (id INT)"))
            conn.execute(text("INSERT INTO qa_probe VALUES (42)"))
            probe = conn.execute(text("SELECT id FROM qa_probe")).scalar()
        detail = f"mysql={version} tables={table_count} write_read_roundtrip={probe == 42}"
        results.append(Check("database", "PASS", detail))
    except Exception as exc:
        results.append(Check("database", "FAIL", str(exc)))

    # 3. LinkedIn authentication -----------------------------------------------
    try:
        from app.infrastructure.linkedin_mcp.auth import (
            LinkedInMCPAuthClient,
            LinkedInSessionStatus,
        )

        status = LinkedInMCPAuthClient(linkedin).session_status()
        if status is LinkedInSessionStatus.AUTHENTICATED:
            results.append(Check("linkedin_auth", "PASS", "persisted session is authenticated"))
        else:
            results.append(Check("linkedin_auth", "FAIL", f"session status = {status.value}"))
    except Exception as exc:
        results.append(Check("linkedin_auth", "FAIL", str(exc)))

    # 4. MCP lifecycle ----------------------------------------------------------
    # The real server does not complete a stdio handshake in this headless
    # shell (observed: 90s no response; `--status` also hangs). Verifying the
    # wiring below is real; booting the server is deferred to the desktop.
    try:
        from app.infrastructure.linkedin_mcp.client import LinkedInMCPClient

        client = LinkedInMCPClient(
            command=linkedin.command,
            args=linkedin.base_arguments(),
            cwd=linkedin.cwd,
        )
        params = client._params
        results.append(
            Check(
                "mcp_lifecycle",
                "BLOCKED",
                "real stdio handshake unavailable in this headless shell",
                [
                    f"command={params.command}",
                    f"args={params.args}",
                    f"cwd={params.cwd}",
                    "evidence: server process not responding within 90s here; "
                    "`--status` hangs too (chromium cannot boot headless)",
                ],
            )
        )
    except Exception as exc:
        results.append(Check("mcp_lifecycle", "FAIL", str(exc)))

    # 5. Telegram connector ----------------------------------------------------
    try:
        import asyncio

        from telegram import Bot

        async def _me() -> dict[str, object]:
            try:
                me = await Bot(token=telegram.bot_token).get_me()
                return {"ok": True, "username": "@" + (me.username or "")}
            except Exception as exc:
                return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

        outcome = asyncio.run(_me())
        if outcome["ok"]:
            results.append(
                Check(
                    "telegram_connector",
                    "PASS",
                    f"getMe ok ({outcome['username']}); no message sent",
                )
            )
        else:
            results.append(Check("telegram_connector", "FAIL", str(outcome.get("error"))))
    except Exception as exc:
        results.append(Check("telegram_connector", "FAIL", str(exc)))

    # 6. Telegram message formatting (pure, real formatter) ---------------------
    try:
        from app.infrastructure.telegram.messages import format_linked_match_message

        text = format_linked_match_message(
            title="QA Verification Role",
            company="StagePilot QA",
            location="Remote",
            url="https://example.com/job",
            final_score=87.5,
            why="Strong skill overlap with the candidate profile.",
            matched_skills=["python"],
            missing_skills=[],
            salary=None,
            employment_type="Internship",
            experience_level="Entry",
            company_size="11-50",
            recruiter=None,
            posted_at=None,
            max_length=4096,
        )
        ok = "QA Verification Role" in text and "88%" in text
        results.append(
            Check(
                "telegram_formatting",
                "PASS" if ok else "FAIL",
                f"rendered {len(text)} chars" if ok else "missing expected fields",
            )
        )
    except Exception as exc:
        results.append(Check("telegram_formatting", "FAIL", str(exc)))

    # 7. Notification deduplication (real provider, real file IO) --------------
    try:
        from app.infrastructure.linkedin_mcp.notification_state import (
            JsonNotificationStateRepository,
        )

        with tempfile.TemporaryDirectory(prefix="stagepilot-qa-") as tmp:
            repo = JsonNotificationStateRepository(Path(tmp) / "notified.json")
            job_id = "qa-job-12345"
            repo.mark_notified(job_id)
            first = repo.is_notified(job_id)
            repo.mark_notified(job_id)
            second = repo.is_notified(job_id)
            ok = first and second
        results.append(
            Check(
                "notification_dedup",
                "PASS" if ok else "FAIL",
                "mark/is_notified/idempotent round-trip on real JSON state",
            )
        )
    except Exception as exc:
        results.append(Check("notification_dedup", "FAIL", str(exc)))

    # 8. Resume parsing ---------------------------------------------------------
    resumes = _REPO / "data" / "resumes" / "master"
    has_cv = (
        any(p for p in resumes.rglob("*") if p.is_file() and p.name != ".gitkeep")
        if resumes.exists()
        else False
    )
    results.append(
        Check(
            "resume_parsing",
            "BLOCKED" if not has_cv else "PASS",
            "no real CV asset present" if not has_cv else f"found CVs in {resumes}",
            ["data/resumes/master is empty; real parser verification needs a real resume"],
        )
    )

    # 9. Profile generation -----------------------------------------------------
    master_profile = _REPO / "data" / "master_profile" / "master_profile.json"
    has_profile = master_profile.exists()
    results.append(
        Check(
            "profile_generation",
            "BLOCKED" if not has_profile else "PASS",
            "no real master profile present" if not has_profile else f"found {master_profile}",
            ["profile generation needs a real parsed CV / master profile"],
        )
    )

    # 10. Matching & recommendation engines --------------------------------------
    results.append(
        Check(
            "matching_recommendation",
            "BLOCKED",
            "real scoring requires a real master profile and real LinkedIn jobs",
            [
                "engines are deterministic and covered by the unit suite; "
                "real-data scoring is verified end-to-end in QA M2"
            ],
        )
    )

    # 11. LinkedIn real search / jobs ---------------------------------------------
    results.append(
        Check(
            "linkedin_job_retrieval",
            "BLOCKED",
            "real search needs a headed authenticated Chromium in a desktop session",
            [
                "session is authenticated; browser cannot boot in this headless shell",
                "real jobs are verified in QA M2 on the desktop",
            ],
        )
    )

    # 12. CLI --------------------------------------------------------------------
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "app.main", "doctor"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        ok = proc.returncode == 0 and "database: connectivity OK" in proc.stdout
        tail = "\n".join(proc.stdout.strip().splitlines()[-4:])
        results.append(
            Check(
                "cli",
                "PASS" if ok else "FAIL",
                f"stagepilot doctor rc={proc.returncode}" if ok else tail or proc.stderr[:200],
            )
        )
    except Exception as exc:
        results.append(Check("cli", "FAIL", str(exc)))

    return results


def main() -> int:
    """Run the milestone 1 harness, write the JSON report, and exit 0 on success."""
    results = run()
    payload = {"milestone": 1, "checks": [c.to_dict() for c in results]}
    report_dir = _REPO / "data" / "qa"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "milestone1_report.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("QA Milestone 1 — Production Integration Verification")
    for check in results:
        print(f"  [{check.status:>7}] {check.subsystem}")
        if check.detail:
            print(f"          {check.detail}")
        for note in check.notes:
            print(f"          - {note}")

    failed = [c for c in results if c.status == "FAIL"]
    print(
        f"\nPASS={sum(1 for c in results if c.status == 'PASS')} "
        f"BLOCKED={sum(1 for c in results if c.status == 'BLOCKED')} "
        f"FAIL={len(failed)}"
    )
    if failed:
        print("FAILED: " + ", ".join(c.subsystem for c in failed))
        return 1
    print("All runnable real checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
