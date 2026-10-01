---
name: project-start
description: Pre-build checklist for projects with user accounts or payments - surfaces architectural and security decisions before any code is written.
---

# Project Start Checklist

Use when the user says "project-start", "/project-start", "starting a new project", "new project checklist", or "what do I need to set up before building".

Before we build anything, answer two questions:

1. Does this project have user accounts / authentication?
2. Does it handle payments?

Then use the relevant checklist below.

---

## Always

- **Separate domains** - Use `api.[domain]` for backend, `app.[domain]` for frontend. Recommendation: do this from day one. Reason: auth cookies scope correctly and CORS is never a retrofit problem.
- **Document user flows first** - Run `/spec` or `/prd` and fill in the User Flows section before writing code. Recommendation: do this before any implementation. Reason: gaps in flows become auth bugs and missing edge cases in production.

---

## If user accounts

- **Auth strategy** - Stateless JWT vs. server-side sessions. Recommendation: JWT. Reason: easier to scale and simpler to test concurrently (no shared session store).
- **Supabase auth pattern** (if using Supabase) - signup creates a user ID; every user-facing table has a `user_id` column; every table has an RLS policy `auth.uid() = user_id`. Recommendation: set this up before inserting any data. Reason: retrofitting RLS onto populated tables is error-prone and leaves a window of exposure.
- **Never use the service role key for regular queries** - Use the anon or user-scoped key in your app. Recommendation: keep the service role key server-side only. Reason: the service role bypasses RLS entirely - one leaked key exposes all user data.
- **Write a concurrency test** - Simulate two users accessing the same resource simultaneously. Recommendation: write this before launch. Reason: race conditions in user data are silent and hard to reproduce in prod.

---

## If payments

- **Mirror Stripe data locally** - Create a `subscriptions` table that syncs from Stripe webhooks. Recommendation: never query the Stripe API in the request path for subscription status. Reason: Stripe API latency and downtime become your app's latency and downtime.

---

Next step: run `/spec` to write the first feature spec.
