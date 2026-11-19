"""Human-in-the-loop approval rules."""

from dataclasses import dataclass
from enum import Enum

from travel_planner.shared.exceptions import InvalidApprovalError

MAX_FEEDBACK_LENGTH = 2000


@dataclass(frozen=True)
class ApprovalDecision:
    """A reviewer's decision about a draft itinerary. Always valid once created."""

    approved: bool
    feedback: str = ""

    def __post_init__(self):
        if not isinstance(self.approved, bool):
            raise InvalidApprovalError("'approved' must be true or false")
        feedback = str(self.feedback or "").strip()
        object.__setattr__(self, "feedback", feedback)  # store the trimmed text

        if not self.approved and not feedback:
            raise InvalidApprovalError("Please give feedback explaining what should change.")
        if len(feedback) > MAX_FEEDBACK_LENGTH:
            raise InvalidApprovalError(f"Feedback must be at most {MAX_FEEDBACK_LENGTH} characters.")

    @classmethod
    def from_payload(cls, payload) -> "ApprovalDecision":
        """Build a decision from the dict that resumes the paused workflow."""
        if not isinstance(payload, dict) or "approved" not in payload:
            raise InvalidApprovalError("The approval answer must contain 'approved'")
        return cls(approved=payload["approved"], feedback=payload.get("feedback", ""))

    def to_payload(self) -> dict:
        return {"approved": self.approved, "feedback": self.feedback}


class NextStep(str, Enum):
    REVISE = "revise"      # write a new draft using the feedback
    FINALIZE = "finalize"  # produce the final plan


# SOLID - SRP: only decides whether to revise or finalise (the revision limit).
class RevisionPolicy:
    """Business rule: a rejected draft is revised at most `max_revisions` times."""

    def __init__(self, max_revisions: int = 2):
        if max_revisions < 0:
            raise ValueError("max_revisions cannot be negative")
        self._max_revisions = max_revisions

    def next_step(self, decision: ApprovalDecision, revisions_done: int) -> NextStep:
        if decision.approved:
            return NextStep.FINALIZE
        if revisions_done < self._max_revisions:
            return NextStep.REVISE
        return NextStep.FINALIZE  # limit reached: finalise and apply the feedback directly
