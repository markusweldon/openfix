# OpenFix demo target application

Intentionally vulnerable Node app used as the remediation target for OpenFix demos.

**Do not deploy.** Issues include path traversal, reflected XSS, hardcoded secret, and outdated dependencies.

Live target: push/maintain as its own GitHub repo and set local `OPENFIX_TARGET_REPO` to that URL (or run the OpenFix Action *in* that repo so `GITHUB_REPOSITORY` is the target).
