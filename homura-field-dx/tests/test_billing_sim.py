import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hoa_field.billing_sim import FakeProvider, Handler, ProviderSub

DAY = 86400; T0 = 1_000_000


def mk(grace=3):
    p = FakeProvider(); p.set(ProviderSub("s1", "active", T0 + 30 * DAY, 1)); return p, Handler(p, grace_days=grace)


class Billing(unittest.TestCase):
    def test_grace_days_is_required(self):
        with self.assertRaises(TypeError): Handler(FakeProvider())   # undecided policy must not default

    def test_duplicate_event_processed_once(self):
        p, h = mk(); e = {"id": "evt_1", "sub_id": "s1"}
        self.assertEqual(h.handle(e, T0), "applied"); self.assertEqual(h.handle(e, T0), "duplicate")
        self.assertEqual(h.handle(dict(e), T0 + 5), "duplicate")
        self.assertTrue(h.entitlements["s1"].allowed)

    def test_out_of_order_events_converge_to_authoritative_state(self):
        p, h = mk()
        p.set(ProviderSub("s1", "past_due", T0 + 30 * DAY, 3))        # latest: payment failed
        h.handle({"id": "evt_new", "sub_id": "s1"}, T0 + 31 * DAY)    # newer event arrives first
        p.set(ProviderSub("s1", "past_due", T0 + 30 * DAY, 3))
        h.handle({"id": "evt_old_paid", "sub_id": "s1"}, T0 + 31 * DAY)  # older 'paid' event arrives late
        e = h.entitlements["s1"]
        self.assertEqual(e.based_on_version, 3); self.assertTrue(e.allowed)   # within 3-day grace
        self.assertIn("grace", e.reason)

    def test_payment_failure_beyond_grace_denied(self):
        p, h = mk(grace=3); p.set(ProviderSub("s1", "past_due", T0 + 30 * DAY, 2))
        h.handle({"id": "e1", "sub_id": "s1"}, T0 + 30 * DAY + 4 * DAY)
        self.assertFalse(h.entitlements["s1"].allowed)

    def test_zero_grace_denies_immediately_after_period(self):
        p, h = mk(grace=0); p.set(ProviderSub("s1", "past_due", T0 + 30 * DAY, 2))
        h.handle({"id": "e1", "sub_id": "s1"}, T0 + 30 * DAY)
        self.assertFalse(h.entitlements["s1"].allowed)

    def test_recovery_after_failure(self):
        p, h = mk(); p.set(ProviderSub("s1", "past_due", T0 + 30 * DAY, 2)); h.handle({"id": "e1", "sub_id": "s1"}, T0 + 40 * DAY)
        self.assertFalse(h.entitlements["s1"].allowed)
        p.set(ProviderSub("s1", "active", T0 + 60 * DAY, 4)); h.handle({"id": "e2", "sub_id": "s1"}, T0 + 41 * DAY)
        self.assertTrue(h.entitlements["s1"].allowed)

    def test_stale_state_never_regresses(self):
        p, h = mk(); p.set(ProviderSub("s1", "active", T0 + 60 * DAY, 5)); h.handle({"id": "e1", "sub_id": "s1"}, T0)
        p.set(ProviderSub("s1", "past_due", T0 + 30 * DAY, 2))     # stale read from a lagging replica
        self.assertEqual(h.handle({"id": "e2", "sub_id": "s1"}, T0 + 50 * DAY), "stale-ignored")
        self.assertTrue(h.entitlements["s1"].allowed)

    def test_canceled_keeps_access_until_period_end_only(self):
        p, h = mk(); p.set(ProviderSub("s1", "canceled", T0 + 10 * DAY, 2))
        h.handle({"id": "e1", "sub_id": "s1"}, T0 + 5 * DAY); self.assertTrue(h.entitlements["s1"].allowed)
        h.handle({"id": "e2", "sub_id": "s1"}, T0 + 11 * DAY); self.assertFalse(h.entitlements["s1"].allowed)

    def test_unknown_status_denied(self):
        p, h = mk(); p.set(ProviderSub("s1", "weird", T0, 2)); h.handle({"id": "e1", "sub_id": "s1"}, T0)
        self.assertFalse(h.entitlements["s1"].allowed)


if __name__ == "__main__":
    unittest.main()
