---
name: note
description: Log a human observation for the project retrospective (what went wrong, what the plugin missed, a good idea). Recorded before Claude reads it.
argument-hint: "#tag nội dung (tags gợi ý: #spec #estimate #design #build #review #ship #plugin #token #khach)"
disable-model-invocation: true
allowed-tools: Bash
---

```!
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dk_event.py" note <<'DK_NOTE_EOF'
$ARGUMENTS
DK_NOTE_EOF
```

Reply with the line above only. Do not comment on the note or start any work.
