import pytest

from travel_planner.shared.exceptions import InvalidApprovalError
from travel_planner.workflow.approval import MAX_FEEDBACK_LENGTH, ApprovalDecision, NextStep, RevisionPolicy


# ------------------------------------------------------------------ ApprovalDecision
def test_approval_without_feedback_is_valid():
    decision = ApprovalDecision(approved=True)
    assert decision.approved and decision.feedback == ""


def test_feedback_is_trimmed():
    assert ApprovalDecision(False, "  add Kyoto  ").feedback == "add Kyoto"


@pytest.mark.parametrize("feedback", ["", "   "])
def test_rejection_requires_feedback(feedback):
    with pytest.raises(InvalidApprovalError, match="feedback"):
        ApprovalDecision(approved=False, feedback=feedback)


def test_feedback_length_boundaries():
    assert ApprovalDecision(False, "x" * MAX_FEEDBACK_LENGTH)
    with pytest.raises(InvalidApprovalError):
        ApprovalDecision(False, "x" * (MAX_FEEDBACK_LENGTH + 1))


def test_approved_must_be_a_real_boolean():
    with pytest.raises(InvalidApprovalError):
        ApprovalDecision(approved="yes", feedback="")  # type: ignore[arg-type]


def test_payload_round_trip():
    decision = ApprovalDecision(False, "cheaper hotels")
    assert ApprovalDecision.from_payload(decision.to_payload()) == decision


@pytest.mark.parametrize("payload", [None, "yes", {}, {"feedback": "x"}, {"approved": "true"}])
def test_invalid_payloads_are_rejected(payload):
    with pytest.raises(InvalidApprovalError):
        ApprovalDecision.from_payload(payload)


# ------------------------------------------------------------------ RevisionPolicy
policy = RevisionPolicy(max_revisions=2)


def test_approved_plan_is_finalised():
    assert policy.next_step(ApprovalDecision(True), revisions_done=0) is NextStep.FINALIZE


@pytest.mark.parametrize("revisions_done", [0, 1])
def test_rejected_plan_is_revised_while_revisions_remain(revisions_done):
    assert policy.next_step(ApprovalDecision(False, "change"), revisions_done) is NextStep.REVISE


def test_rejected_plan_is_finalised_with_feedback_when_limit_reached():
    assert policy.next_step(ApprovalDecision(False, "change"), revisions_done=2) is NextStep.FINALIZE


def test_zero_revisions_policy_never_revises():
    assert RevisionPolicy(0).next_step(ApprovalDecision(False, "change"), 0) is NextStep.FINALIZE


def test_negative_limit_is_invalid():
    with pytest.raises(ValueError):
        RevisionPolicy(-1)
