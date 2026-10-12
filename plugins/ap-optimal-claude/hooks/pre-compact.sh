#!/bin/bash
# Auto-save handoff before context compaction
# (Touched in 1.9.4 so Windows clones with CRLF line endings get it re-checked-out as LF.)
echo '{"systemMessage":"Context compaction is about to occur. Before compacting, immediately run the handoff skill and save docs/SESSION_HANDOFF.md for this project. Do this now - write the full handoff file first, then compaction can proceed."}'
