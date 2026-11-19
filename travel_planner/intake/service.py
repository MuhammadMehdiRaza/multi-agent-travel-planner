"""Intake service: validate -> guardrail -> route. (Module 1 entry point.)"""

from dataclasses import dataclass

from travel_planner.domain.models import RoutingDecision
from travel_planner.intake.guardrail import InputGuardrail
from travel_planner.intake.routing import RoutingStrategy
from travel_planner.intake.validation import RequestValidator
from travel_planner.shared.exceptions import InvalidRequestError


@dataclass(frozen=True)
class IntakeOutcome:
    accepted: bool
    query: str
    rejection_reason: str = ""
    decision: RoutingDecision | None = None


# Strategy pattern: IntakeService is the context; it uses whichever RoutingStrategy it is given.
# SOLID - SRP: validation, guardrail and routing are separate classes; this one only orders them.
# SOLID - DIP: depends on the InputGuardrail and RoutingStrategy abstractions (injected).
class IntakeService:
    """Decides whether a request is accepted and, if so, which agents should handle it.

    All three collaborators are injected through the constructor (Dependency
    Inversion), so each one can be replaced or faked independently.
    """

    def __init__(self, validator: RequestValidator, guardrail: InputGuardrail, router: RoutingStrategy):
        self._validator = validator
        self._guardrail = guardrail
        self._router = router

    def process(self, raw_query: str) -> IntakeOutcome:
        # Step 1: cheap deterministic checks (no LLM cost).
        try:
            query = self._validator.validate(raw_query)
        except InvalidRequestError as error:
            return IntakeOutcome(accepted=False, query=str(raw_query), rejection_reason=str(error))

        # Step 2: LLM guardrail - is this really a travel request?
        verdict = self._guardrail.check(query)
        if not verdict.allowed:
            return IntakeOutcome(accepted=False, query=query, rejection_reason=verdict.reason)

        # Step 3: choose the agents.
        decision = self._router.route(query)
        return IntakeOutcome(accepted=True, query=query, decision=decision)
