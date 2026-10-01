#!/bin/bash
# PostToolUse (Task|Agent): state, as a fact, how much observing a delegate did
# before it reported back.
#
# Why this exists
# ---------------
# The orchestrating agent reliably relays delegate findings to the user in the
# same confident voice it uses for things it checked itself. Documents telling
# it not to have failed repeatedly, in more than one project. The interception
# point is the moment the delegate's result lands, before the orchestrator acts
# on it - which is this event.
#
# It injects a MEASUREMENT, not an instruction. `totalToolUseCount` is in the
# tool response, so "this delegate made 0 tool calls" is simply true and can
# never cry wolf. A reminder that nags on every delegate return trains ritual
# compliance and gets tuned out; a fact does not.
#
# Fragility, stated plainly
# -------------------------
# The hooks reference says the Task/Agent tool does NOT surface in PreToolUse or
# PostToolUse. Measured against CLI 2.1.222 it does: this hook fires with
# tool_name="Agent" and a full tool_response. That is undocumented behaviour and
# may stop working on any update. When it does, this hook simply goes silent -
# it never blocks and never errors. `scripts/test_delegate_findings_note.py
# --live` is the canary that tells you it has stopped.
#
# Never exec, never let a non-zero status escape: on PostToolUse a non-zero exit
# surfaces an error to the model for no reason.
command -v python3 >/dev/null 2>&1 || exit 0

INPUT=$(cat)

# Quoted heredoc: nothing inside is expanded by the shell, so apostrophes and
# quotes in the body are safe. The payload travels via the environment.
HOOK_INPUT="$INPUT" python3 <<'PY' || true
import json, os, sys

try:
    d = json.loads(os.environ.get("HOOK_INPUT") or "")
except Exception:
    sys.exit(0)

if not isinstance(d, dict):
    sys.exit(0)

resp = d.get("tool_response")
if not isinstance(resp, dict):
    sys.exit(0)

# Only speak when the payload actually carries the counter we report on.
calls = resp.get("totalToolUseCount")
if not isinstance(calls, int):
    sys.exit(0)

agent = resp.get("agentType") or d.get("agent_type") or "subagent"
tokens = resp.get("totalTokens")

# Length of the delegate final message, for the ratio that matters: a long
# report built on no observation is the shape worth noticing.
chars = 0
content = resp.get("content")
if isinstance(content, list):
    for block in content:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            chars += len(block["text"])
elif isinstance(content, str):
    chars = len(content)

facts = "delegate " + str(agent) + " returned " + str(chars) + " characters after " + str(calls) + " tool call"
if calls != 1:
    facts += "s"
if isinstance(tokens, int):
    facts += " and " + str(tokens) + " tokens"
facts += "."

note = "DELEGATE RESULT - " + facts

if calls == 0 and chars > 0:
    note += (
        " It opened nothing, so everything above is inference, not observation."
        " Reproduce anything load-bearing against the real artifact before relaying it or acting on it,"
        " and say which parts you reproduced and which you are passing on unverified."
    )

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": note,
    },
    "suppressOutput": True,
}))
PY

exit 0
