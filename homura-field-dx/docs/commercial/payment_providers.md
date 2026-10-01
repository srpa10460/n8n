# Payment provider comparison (research only; NO account created, NO real transaction)

Date of research: 2026-10-01. Purpose: choose a TEST-environment path for the subscription preparation. Selection and any account creation need 伊佐's approval (stop condition).

## How the facts were obtained (read this before trusting any number)
Direct fetching of stripe.com / docs.stripe.com / pay.jp was BLOCKED by this sandbox's egress proxy. The figures below come from web-search summaries of the OFFICIAL pages (URLs listed). They are second-hand: a Human must re-check them on the live official pages before any decision. Terms for consumption tax, minimums, review/onboarding and payout timing were NOT retrieved.

| Item | Stripe (Japan) | PAY.JP |
|------|----------------|--------|
| Card fee | 3.6% per successful card payment (+2% if currency conversion) | Standard plan 3.3% (monthly sales < 4M JPY); Business 2.78% (4M-20M); Enterprise 2.59-2.7% (>= 20M) |
| Subscription | Stripe Billing: payment fee 3.6% per successful card charge; Billing pricing is usage-based "depending on capabilities" (details not retrieved) | Monthly / yearly recurring billing; integrated with Webhook; no separate recurring fee stated in the summary |
| Fixed fees | none stated in the summary | initial 0, refund 0, transaction 0 JPY; pay-per-sale |
| Test environment | Stripe has test mode (standard, from general knowledge; not re-verified this session) | Recurring billing works in test mode and cycles behave like production (help.pay.jp article) |
| Webhook duplicates / order | Docs: events can be received more than once; delivery order is NOT guaranteed; track processed event ids; do not use `created` for ordering | Docs: same webhook can be sent multiple times; non-2xx / 10 s timeout / connection error => automatic retry every 3 minutes up to 3 times; handle by event-id cache or idempotent logic |
| API idempotency | Idempotent requests documented | Idempotent requests documented (unique key per request) |

## Implication for our design (verified by simulation, provider-neutral)
Treat a webhook as a trigger only: skip seen event ids, re-read the authoritative subscription from the provider API, derive entitlement from that state, never move to an older provider state version. Implemented and tested in `src/hoa_field/billing_sim.py` / `tests/test_billing_sim.py` (9 tests: duplicate, out-of-order, payment failure inside/outside grace, recovery, stale read, cancel at period end, unknown status). Real-provider test-mode integration is NOT done.

## Not decided / not researched (🔳)
- Which provider (needs: tax invoicing needs, Japan business registration status of the seller, payout timing, onboarding review). Merchant-of-record alternatives were not examined.
- Grace period for failed payments (policy): the handler requires it as an explicit argument.
- Invoice/receipt requirements for Japanese B2B (qualified invoice system) were not researched.

## Sources (official pages, via search summary; re-verify)
- https://stripe.com/en-jp/pricing , https://stripe.com/en-jp/billing/pricing
- https://docs.stripe.com/webhooks
- https://pay.jp/plan , https://pay.jp/docs/subscription , https://docs.pay.jp/v1/webhook , https://docs.pay.jp/v2/guide/developers/event-webhook , https://docs.pay.jp/v2/guide/developers/idempotency
- https://help.pay.jp/ja/articles/3438283 (test mode recurring billing)
