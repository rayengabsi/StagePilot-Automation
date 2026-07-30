from __future__ import annotations

from app.domain.approval.enums import ApprovalState, is_valid_transition


def test_valid_transitions_from_new() -> None:
    assert is_valid_transition(ApprovalState.NEW, ApprovalState.QUEUED)
    assert is_valid_transition(ApprovalState.NEW, ApprovalState.ARCHIVED)
    assert not is_valid_transition(ApprovalState.NEW, ApprovalState.APPROVED)
    assert not is_valid_transition(ApprovalState.NEW, ApprovalState.REJECTED)
    assert not is_valid_transition(ApprovalState.NEW, ApprovalState.UNDER_REVIEW)


def test_valid_transitions_from_queued() -> None:
    assert is_valid_transition(ApprovalState.QUEUED, ApprovalState.UNDER_REVIEW)
    assert is_valid_transition(ApprovalState.QUEUED, ApprovalState.ARCHIVED)
    assert is_valid_transition(ApprovalState.QUEUED, ApprovalState.SKIPPED)
    assert not is_valid_transition(ApprovalState.QUEUED, ApprovalState.APPROVED)
    assert not is_valid_transition(ApprovalState.QUEUED, ApprovalState.REJECTED)


def test_valid_transitions_from_under_review() -> None:
    assert is_valid_transition(ApprovalState.UNDER_REVIEW, ApprovalState.APPROVED)
    assert is_valid_transition(ApprovalState.UNDER_REVIEW, ApprovalState.REJECTED)
    assert is_valid_transition(ApprovalState.UNDER_REVIEW, ApprovalState.REVISION_REQUESTED)
    assert is_valid_transition(ApprovalState.UNDER_REVIEW, ApprovalState.SKIPPED)
    assert is_valid_transition(ApprovalState.UNDER_REVIEW, ApprovalState.ARCHIVED)
    assert not is_valid_transition(ApprovalState.UNDER_REVIEW, ApprovalState.NEW)
    assert not is_valid_transition(ApprovalState.UNDER_REVIEW, ApprovalState.QUEUED)


def test_valid_transitions_from_approved() -> None:
    assert is_valid_transition(ApprovalState.APPROVED, ApprovalState.ARCHIVED)
    assert not is_valid_transition(ApprovalState.APPROVED, ApprovalState.REJECTED)
    assert not is_valid_transition(ApprovalState.APPROVED, ApprovalState.QUEUED)


def test_valid_transitions_from_rejected() -> None:
    assert is_valid_transition(ApprovalState.REJECTED, ApprovalState.ARCHIVED)
    assert is_valid_transition(ApprovalState.REJECTED, ApprovalState.QUEUED)
    assert not is_valid_transition(ApprovalState.REJECTED, ApprovalState.APPROVED)


def test_valid_transitions_from_revision_requested() -> None:
    assert is_valid_transition(ApprovalState.REVISION_REQUESTED, ApprovalState.QUEUED)
    assert is_valid_transition(ApprovalState.REVISION_REQUESTED, ApprovalState.ARCHIVED)
    assert not is_valid_transition(ApprovalState.REVISION_REQUESTED, ApprovalState.APPROVED)


def test_valid_transitions_from_skipped() -> None:
    assert is_valid_transition(ApprovalState.SKIPPED, ApprovalState.ARCHIVED)
    assert is_valid_transition(ApprovalState.SKIPPED, ApprovalState.QUEUED)


def test_valid_transitions_from_archived() -> None:
    assert not is_valid_transition(ApprovalState.ARCHIVED, ApprovalState.NEW)
    assert not is_valid_transition(ApprovalState.ARCHIVED, ApprovalState.QUEUED)
    assert not is_valid_transition(ApprovalState.ARCHIVED, ApprovalState.APPROVED)


def test_all_states_covered() -> None:
    all_states = list(ApprovalState)
    for state in all_states:
        assert state in is_valid_transition.__globals__["VALID_TRANSITIONS"]


def test_no_self_transitions() -> None:
    for state in ApprovalState:
        assert not is_valid_transition(state, state)
