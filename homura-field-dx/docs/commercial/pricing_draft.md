# Pricing / contract / operations draft (STRUCTURE ONLY - no price is proposed yet)

Why no yen amounts: the price must be grounded in running cost, provided scope and support scope (instruction). None of those inputs exist yet: the VPS is not chosen or contracted, support hours are not defined, and the target devices are not decided. Inventing numbers would be fabrication. The formula and the inputs 伊佐 must supply are below. First candidate contractor: Mina-san - no contractor details exist in this repo and none were invented; no billing has started.

## 1. Provided scope (what the subscription includes) - facts from the current build
- A: field app (offline-capable PWA), catalog, measurement, photos, validation, interference check, preview, review/approval, export, manual sync with a server.
- Server side of sync: storage of projects and photos (grows with photo volume).
- NOT included / not built: photo-to-draft automation, dimension constraints, B (Blender production) delivery as a service, real authentication, HTTPS hosting.
Scope tiers are only meaningful after the above gaps are decided.

## 2. Cost model (monthly, per customer)
price = ( infra_share + storage_share + support_cost + payment_fee_base ) / ( 1 - payment_rate - margin )
- infra_share = VPS monthly cost / number of customers sharing it  (VPS cost: UNKNOWN)
- storage_share = photo GB per project x projects per month x storage unit cost  (photo volume: UNKNOWN; per-photo limit in the app is 8 MB)
- support_cost = included support hours x internal hourly cost  (included hours: UNDEFINED)
- payment_rate = provider card rate from payment_providers.md (Stripe JP 3.6%, PAY.JP Standard 3.3%; to be re-verified)
- margin = target margin (UNDECIDED)

## 3. Support scope options (to choose)
(a) none beyond the manual (b) email, business days, response target T (c) onboarding session + email. Each needs defined hours and response time before pricing.

## 4. Contract terms to prepare (drafts only after 🔳 inputs; legal review is outside this session)
Term/renewal, cancellation timing (the entitlement model grants access until paid period end), failed-payment grace days (policy input required by the code), data retention/deletion after cancellation, data ownership/export (the app has a recovery export), liability limits, support hours, availability statement (cannot be written: no hosting yet).

## 5. Sales screen / entitlement linkage plan (test environment only)
1) Provider test mode account (needs 伊佐's approval) 2) webhook endpoint = trigger + authoritative fetch (billing_sim.py design) 3) entitlement flag read by sync endpoints (not built) 4) tests: duplicate, reorder, failure, recovery (simulated: done; with real test-mode provider: not done).

## 6. Operations design inputs still missing
VPS spec/location, HTTPS domain, backup policy for server_projects/server_assets, auth scheme, monitoring, incident contact, who operates.

🔳 Inputs needed from 伊佐: VPS choice/cost, expected customers & photo volume, support scope & hours, margin target, grace days, provider choice, contractor details for Mina-san (to be supplied by 伊佐; never inferred).
