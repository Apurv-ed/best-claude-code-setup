---
name: open-source-audit
description: Audit codebase for areas where well-maintained open-source libraries would be more robust than custom code. Use at project start or periodically.
---

# Open Source Audit

- Proactively audit the codebase for areas where a highly respected, well-maintained open-source library or tool would be more robust than custom code.
- Evaluate: is any custom implementation reinventing something that a battle-tested library handles better (retry logic, parsing, validation, auth, etc.)?
- **Before recommending a replacement, run a rigorous adversarial simulation:** trace through existing tests, check for exception type changes, mock compatibility, log message assertions, and behavioral differences. Calculate the real migration cost vs. the actual robustness gain.
- **Do not recommend replacements for the sake of it.** Only recommend when the library genuinely solves a problem the current code has (bugs, fragility, missing features) - not just because it exists.
- Present findings as: what is already good (no change needed), what is worth adopting (with honest risk assessment), and what to consider later (not urgent).
