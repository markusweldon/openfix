# OpenFix demo target application

Intentionally vulnerable Node app used as the remediation target for OpenFix demos.

**Do not deploy.** Issues include path traversal, reflected XSS, hardcoded secret, and outdated `lodash` / `express`.

For cloud agent demos, push this directory (or the whole OpenFix repo) to GitHub and set `OPENFIX_TARGET_REPO` to that URL.
