---
name: end-session
description: Use when the user types "end session" or wants to wrap up and close for the day. Runs the full "update docs" pass, writes a handoff note only if work is unfinished, then "update github" (commit and push), and ends with a short summary.
---

# End Session

One phrase that saves everything properly before the user closes Claude Code. Run the steps in order. Do not ask for confirmation between steps; stop only on a real problem (see the end).

1. **Full docs pass.** Do steps 1-5 of "update docs" in the ap-optimal-claude:project-docs skill (every changed fact in its one home, instruction-file audit, docs checked against the code, decisions, doc check). Skip its step 6 commit: step 3 below makes one commit for everything.
2. **Handoff, only if work is unfinished.** If anything from this session is half-done, broken, or waiting on the user, invoke the ap-optimal-claude:handoff skill now, so the note is committed and pushed with the rest instead of living only on this computer. Skip the handoff skill's closing message ("type /exit ...") - step 4 replaces it. If nothing is unfinished, STATUS.md already is the handoff: delete a stale `docs/SESSION_HANDOFF.md` if one exists.
3. **Update GitHub.** Follow "update github": the project CLAUDE.md version if it defines one, otherwise the ap-optimal-claude:update-github skill. Skip its doc-update step and its handoff step (steps 1-2 above did them). Add the line `docs(audit): full docs pass at end of session` to the commit body, so the next "update docs" knows where to start.
4. **Summary.** At most 3 plain lines: what was saved, whether a handoff note was written, and anything that needs the user. Then: "All saved. You can close this session."

## When Things Go Wrong

- **Push fails, or a commit hook blocks:** stop, show the exact error, and do not force anything. The work is still committed locally; say so.
- **Not a git repo:** do steps 1-2, then say the project has no GitHub copy yet and offer to create a private repo. Do not create one without a yes.
- **Something in the diff looks like a secret or a large file:** do not commit it. Name the file and ask.
