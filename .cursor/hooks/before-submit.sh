#!/usr/bin/env bash
# Remind the agent of separation of duties before each prompt turn.
set -euo pipefail
cat >/dev/null || true
printf '{"continue":true,"user_message":"OpenFix: external scanner detected; remediate only; open a PR; never merge to main."}\n'
