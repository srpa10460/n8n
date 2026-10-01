"""Provider-NEUTRAL entitlement model for subscription sales preparation. NOT connected to any payment provider,
no network, no real money. Purpose: prove the notification-handling design before any provider account exists.

Design (follows what Stripe and PAY.JP docs state: duplicate delivery happens, ordering is not guaranteed, failed
deliveries are retried): a webhook event is only a TRIGGER. The handler (1) skips already-processed event ids and
(2) re-reads the AUTHORITATIVE subscription state from the provider API, then derives the entitlement from that state.
So ordering inversions and duplicates cannot change the outcome, and handling is idempotent.
grace_days is a business policy that has NOT been decided: it is a required argument, with no default."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderSub:               # what the provider's API would return for a subscription
    sub_id: str
    status: str                  # active | past_due | canceled | unpaid
    paid_until: int              # epoch seconds of the end of the paid period
    state_version: int           # monotonic on the provider side


class FakeProvider:
    """Stand-in for the provider API (authoritative state)."""
    def __init__(self): self.subs: dict[str, ProviderSub] = {}
    def set(self, sub: ProviderSub): self.subs[sub.sub_id] = sub
    def retrieve(self, sub_id: str) -> ProviderSub: return self.subs[sub_id]


@dataclass
class Entitlement:
    sub_id: str
    allowed: bool
    reason: str
    based_on_version: int


@dataclass
class Handler:
    provider: FakeProvider
    grace_days: int                                  # REQUIRED policy input (undecided)
    processed: set = field(default_factory=set)
    entitlements: dict = field(default_factory=dict)
    log: list = field(default_factory=list)

    def handle(self, event: dict, now: int) -> str:
        eid = event["id"]
        if eid in self.processed:
            self.log.append(("duplicate-skipped", eid)); return "duplicate"
        sub = self.provider.retrieve(event["sub_id"])         # authoritative state, not the payload
        cur = self.entitlements.get(sub.sub_id)
        if cur and cur.based_on_version > sub.state_version:   # never go backwards
            self.processed.add(eid); return "stale-ignored"
        grace = self.grace_days * 86400
        if sub.status == "canceled":
            ent = Entitlement(sub.sub_id, now < sub.paid_until, "canceled: access until paid period end" if now < sub.paid_until else "canceled", sub.state_version)
        elif sub.status == "active":
            ent = Entitlement(sub.sub_id, True, "active", sub.state_version)
        elif sub.status in ("past_due", "unpaid"):
            ok = now < sub.paid_until + grace
            ent = Entitlement(sub.sub_id, ok, f"payment failed: {'within' if ok else 'beyond'} grace {self.grace_days}d", sub.state_version)
        else:
            ent = Entitlement(sub.sub_id, False, f"unknown status {sub.status}: denied", sub.state_version)
        self.entitlements[sub.sub_id] = ent
        self.processed.add(eid)                               # recorded only after a successful apply
        return "applied"
