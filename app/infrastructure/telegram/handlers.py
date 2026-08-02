from __future__ import annotations

from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler

from app.config.telegram_config import TelegramConfig, get_telegram_config
from app.db.session import create_database_engine, create_session_factory
from app.domain.approval.entities import ApplicationPackage
from app.domain.approval.errors import ApprovalError, UnauthorizedError
from app.infrastructure.telegram.auth import TelegramAuth
from app.infrastructure.telegram.messages import (
    format_application_message,
    format_application_update_message,
    format_document_info_message,
    format_history_message,
    format_queue_message,
    format_snapshot_preview,
    format_status_message,
)
from app.services.approval_service import ApprovalService


def build_handlers() -> list[Any]:
    """Build the list of Telegram bot handlers."""
    return [
        CommandHandler("start", _cmd_start),
        CommandHandler("help", _cmd_help),
        CommandHandler("queue", _cmd_queue),
        CommandHandler("view", _cmd_view),
        CommandHandler("open", _cmd_open),
        CommandHandler("approve", _cmd_approve),
        CommandHandler("reject", _cmd_reject),
        CommandHandler("revise", _cmd_revise),
        CommandHandler("skip", _cmd_skip),
        CommandHandler("archive", _cmd_archive),
        CommandHandler("history", _cmd_history),
        CommandHandler("status", _cmd_status),
        CallbackQueryHandler(_callback_handler),
    ]


def _get_service() -> ApprovalService:
    from app.config.settings import get_settings

    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    session = session_factory()
    return ApprovalService(session=session)


def _get_auth(config: TelegramConfig | None = None) -> TelegramAuth:
    return TelegramAuth(config or get_telegram_config())


def _authorize(update: Update) -> int:
    user_id = update.effective_user.id if update.effective_user else 0
    auth = _get_auth()
    auth.authorize(user_id)
    return user_id


def _build_application_keyboard(package: ApplicationPackage) -> InlineKeyboardMarkup:
    package_id = package.id
    snapshot = _try_parse_json(package.snapshot_json) or {}
    rec = snapshot.get("recommendation", {})
    job = rec.get("job", {}) if isinstance(rec, dict) else {}
    job_url = job.get("url") if isinstance(job, dict) else None

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{package_id}"),
            InlineKeyboardButton("📄 Preview Resume", callback_data=f"resume:{package_id}"),
        ],
        [
            InlineKeyboardButton("✉️ Preview Cover Letter", callback_data=f"cover:{package_id}"),
            InlineKeyboardButton(
                "🔗 Open Job",
                url=str(job_url),
            )
            if job_url
            else InlineKeyboardButton("📋 Package Details", callback_data=f"details:{package_id}"),
        ],
        [
            InlineKeyboardButton("🕘 Application History", callback_data=f"history:{package_id}"),
            InlineKeyboardButton("🧾 Email Draft", callback_data=f"email:{package_id}"),
        ],
        [
            InlineKeyboardButton("🔁 Request Revision", callback_data=f"revise:{package_id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{package_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{package_id}"),
        ],
        [
            InlineKeyboardButton("🗄️ Archive", callback_data=f"archive:{package_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def _cmd_start(update: Update, _context: CallbackContext) -> None:
    if not update.effective_message:
        return
    try:
        _authorize(update)
    except UnauthorizedError:
        await update.effective_message.reply_text("Unauthorized. Please contact an admin.")
        return
    await update.effective_message.reply_text(
        "🚀 *Welcome to StagePilot*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Your approval workspace is ready.\n\n"
        "Use /queue to review recommendations.\n"
        "Use /help for commands.",
        parse_mode="Markdown",
    )


async def _cmd_help(update: Update, _context: CallbackContext) -> None:
    if not update.effective_message:
        return
    try:
        _authorize(update)
    except UnauthorizedError:
        await update.effective_message.reply_text("Unauthorized.")
        return
    await update.effective_message.reply_text(
        "🧭 *StagePilot Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• /queue - Review approval queue\n"
        "• /view <id> - Open recommendation card\n"
        "• /open <id> - Start review\n"
        "• /approve <id> [reason] - Approve\n"
        "• /reject <id> [reason] - Reject\n"
        "• /revise <id> [reason] - Request revision\n"
        "• /skip <id> [reason] - Skip\n"
        "• /archive <id> [reason] - Archive\n"
        "• /history <id> - Application history\n"
        "• /status <id> - Package status",
        parse_mode="Markdown",
    )


async def _cmd_queue(update: Update, _context: CallbackContext) -> None:
    if not update.effective_message:
        return
    try:
        _authorize(update)
    except UnauthorizedError:
        await update.effective_message.reply_text("Unauthorized.")
        return

    svc = _get_service()
    packages = svc.peek_queue(limit=10)
    count = svc.queue_count()

    await update.effective_message.reply_text(
        format_queue_message(packages, count), parse_mode="Markdown"
    )


async def _cmd_view(update: Update, context: CallbackContext) -> None:
    if not update.effective_message:
        return
    try:
        _authorize(update)
    except UnauthorizedError:
        await update.effective_message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /view <package_id>")
        return

    try:
        package_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid package ID.")
        return

    svc = _get_service()
    try:
        package = svc.get_package(package_id)
    except ApprovalError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    text = format_application_message(package)
    keyboard = _build_application_keyboard(package)
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def _cmd_open(update: Update, context: CallbackContext) -> None:
    if not update.effective_message:
        return
    try:
        user_id = _authorize(update)
    except UnauthorizedError:
        await update.effective_message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /open <package_id>")
        return

    try:
        package_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid package ID.")
        return

    svc = _get_service()
    try:
        package = svc.start_review(package_id, actor=str(user_id))
    except ApprovalError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    await update.effective_message.reply_text(
        format_status_message(package),
        parse_mode="Markdown",
    )


async def _cmd_approve(update: Update, context: CallbackContext) -> None:
    await _perform_action(update, context, "approve")


async def _cmd_reject(update: Update, context: CallbackContext) -> None:
    await _perform_action(update, context, "reject")


async def _cmd_revise(update: Update, context: CallbackContext) -> None:
    await _perform_action(update, context, "revise")


async def _cmd_skip(update: Update, context: CallbackContext) -> None:
    await _perform_action(update, context, "skip")


async def _cmd_archive(update: Update, context: CallbackContext) -> None:
    await _perform_action(update, context, "archive")


async def _perform_action(update: Update, context: CallbackContext, action: str) -> None:
    if not update.effective_message:
        return
    try:
        user_id = _authorize(update)
    except UnauthorizedError:
        await update.effective_message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text(f"Usage: /{action} <package_id> [comment]")
        return

    try:
        package_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid package ID.")
        return

    comment = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    svc = _get_service()
    try:
        if action == "approve":
            updated = svc.approve(package_id, actor=str(user_id), comment=comment)
        elif action == "reject":
            updated = svc.reject(package_id, actor=str(user_id), comment=comment)
        elif action == "revise":
            updated = svc.request_revision(package_id, actor=str(user_id), comment=comment)
        elif action == "skip":
            updated = svc.skip(package_id, actor=str(user_id), comment=comment)
        elif action == "archive":
            updated = svc.archive(package_id, actor=str(user_id), comment=comment)
        else:
            await update.effective_message.reply_text(f"Unknown action: {action}")
            return
    except ApprovalError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    await update.effective_message.reply_text(
        format_application_update_message(
            title=f"Package #{package_id}",
            status=updated.status.value,
            comment=f"Action completed: {action}",
        ),
        parse_mode="Markdown",
    )


async def _cmd_history(update: Update, context: CallbackContext) -> None:
    if not update.effective_message:
        return
    try:
        _authorize(update)
    except UnauthorizedError:
        await update.effective_message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /history <package_id>")
        return

    try:
        package_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid package ID.")
        return

    svc = _get_service()
    try:
        events = svc.get_history(package_id)
    except ApprovalError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    await update.effective_message.reply_text(
        format_history_message(package_id, events), parse_mode="Markdown"
    )


async def _cmd_status(update: Update, context: CallbackContext) -> None:
    if not update.effective_message:
        return
    try:
        _authorize(update)
    except UnauthorizedError:
        await update.effective_message.reply_text("Unauthorized.")
        return

    if not context.args:
        await update.effective_message.reply_text("Usage: /status <package_id>")
        return

    try:
        package_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Invalid package ID.")
        return

    svc = _get_service()
    try:
        package = svc.get_package(package_id)
    except ApprovalError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    await update.effective_message.reply_text(format_status_message(package), parse_mode="Markdown")


async def _callback_handler(update: Update, _context: CallbackContext) -> None:
    if not update.callback_query or not update.effective_message:
        return

    query = update.callback_query
    await query.answer()

    try:
        user_id = _authorize(update)
    except UnauthorizedError:
        await query.edit_message_text("Unauthorized.")
        return

    data = query.data
    if not data or ":" not in data:
        return

    action, raw_id = data.split(":", 1)
    try:
        package_id = int(raw_id)
    except ValueError:
        await query.edit_message_text("Invalid package ID.")
        return

    svc = _get_service()

    try:
        if action == "approve":
            updated = svc.approve(package_id, actor=str(user_id))
            await query.edit_message_text(format_status_message(updated), parse_mode="Markdown")
        elif action == "reject":
            updated = svc.reject(package_id, actor=str(user_id))
            await query.edit_message_text(format_status_message(updated), parse_mode="Markdown")
        elif action == "revise":
            updated = svc.request_revision(package_id, actor=str(user_id))
            await query.edit_message_text(format_status_message(updated), parse_mode="Markdown")
        elif action == "skip":
            updated = svc.skip(package_id, actor=str(user_id))
            await query.edit_message_text(format_status_message(updated), parse_mode="Markdown")
        elif action == "archive":
            updated = svc.archive(package_id, actor=str(user_id))
            await query.edit_message_text(format_status_message(updated), parse_mode="Markdown")
        elif action in ("resume", "cover", "email", "details"):
            info = await _get_document_info(svc, package_id, action)
            await query.edit_message_text(info, parse_mode="Markdown")
        elif action == "history":
            events = svc.get_history(package_id)
            await query.edit_message_text(
                format_history_message(package_id, events), parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(f"Unknown action: {action}")
    except ApprovalError as exc:
        await query.edit_message_text(str(exc))


async def _get_document_info(svc: ApprovalService, package_id: int, doc_type: str) -> str:
    if doc_type == "details":
        snapshot = svc.get_snapshot(package_id)
        return format_snapshot_preview(snapshot)
    docs = svc.get_documents(package_id)
    if doc_type == "resume":
        return format_document_info_message(
            title="Resume Preview",
            fields={
                "PDF": docs.get("resume_pdf", ""),
                "DOCX": docs.get("resume_docx", ""),
            },
        )
    if doc_type == "cover":
        return format_document_info_message(
            title="Cover Letter Preview",
            fields={
                "PDF": docs.get("cover_letter_pdf", ""),
                "DOCX": docs.get("cover_letter_docx", ""),
            },
        )
    if doc_type == "email":
        return format_document_info_message(
            title="Email Draft",
            fields={
                "Subject": docs.get("email_subject", ""),
                "Body Preview": docs.get("email_body", "")[:500],
            },
        )
    return "No information available."


def _try_parse_json(raw: str) -> dict[str, Any] | None:
    import json

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, TypeError):
        return None
