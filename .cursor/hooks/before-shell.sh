#!/usr/bin/env bash
# OpenFix preventative control: block destructive / privileged git operations.
# Hooks receive JSON on stdin; emit JSON permission decision on stdout.
set -euo pipefail

input="$(cat || true)"
command="$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"

deny() {
  local reason="$1"
  printf '{"permission":"deny","user_message":%s}\n' "$(printf '%s' "$reason" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')"
  exit 0
}

allow() {
  printf '{"permission":"allow"}\n'
  exit 0
}

# If we cannot parse, fail closed for known-dangerous patterns in raw input.
raw_lower="$(printf '%s' "$input" | tr '[:upper:]' '[:lower:]')"

if printf '%s' "$raw_lower" | grep -Eq 'rm[[:space:]]+(-[a-z]*f|-[a-z]*r)|rm[[:space:]]+-rf|git[[:space:]]+push[[:space:]]+.*(--force|-f)|git[[:space:]]+push[[:space:]]+.*(main|master)|git[[:space:]]+reset[[:space:]]+--hard|dd[[:space:]]+if='; then
  deny "OpenFix hook blocked destructive or main-branch push command"
fi

if printf '%s' "$command" | grep -Eqi 'git[[:space:]]+push'; then
  if printf '%s' "$command" | grep -Eqi '(main|master)'; then
    deny "OpenFix hook: push to main/master denied — open a PR instead"
  fi
  if printf '%s' "$command" | grep -Eqi -- '--force|-f'; then
    deny "OpenFix hook: force-push denied"
  fi
fi

allow
