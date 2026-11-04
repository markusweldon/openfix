# Security policy

Please report vulnerabilities in OpenFix privately through
[GitHub security advisories](https://github.com/markusweldon/openfix/security/advisories/new), not in public issues.

Particularly relevant are any way for repository content, scanner output or model output to:

- write outside the checkout or to a protected path,
- run commands outside the sandbox or reach the network from it,
- read credentials from the OpenFix process,
- or cause a patch to be reported as `verified` when a required check didn't pass.

The `examples/vulnerable-app` directory is intentionally vulnerable test material. Please don't report it.
