# OpenFix findings JSON

Use this format for tools that don't speak SARIF, or to hand-curate findings. `openfix findings REPORT --json`
converts any supported report into it.

```json
{
  "openfix": "findings/v1",
  "findings": [
    {
      "tool": "my-scanner",
      "rule_id": "insecure-deserialization",
      "title": "Untrusted data passed to pickle.loads",
      "message": "request body reaches pickle.loads",
      "severity": "high",
      "category": "sast",
      "cwe": ["CWE-502"],
      "location": { "path": "app/api.py", "start_line": 42, "end_line": 42 }
    },
    {
      "tool": "my-sca",
      "rule_id": "GHSA-p6mc-m468-83gw",
      "title": "Prototype pollution in lodash",
      "severity": "high",
      "category": "sca",
      "advisories": ["CVE-2020-8203"],
      "package": { "name": "lodash", "version": "4.17.15", "ecosystem": "npm",
                   "fixed_versions": ["4.17.19"], "manifest": "package.json" }
    }
  ]
}
```

| Field | Required | |
|---|---|---|
| `tool`, `rule_id`, `title` | yes | |
| `severity` | no (default `medium`) | `critical`, `high`, `medium`, `low`, `info` |
| `category` | no (default `sast`) | `sast`, `sca`, `secrets`, `iac`, `container`, `other` |
| `location` | for code findings | `path` relative to the project directory |
| `package` | for dependency findings | `fixed_versions` enables deterministic upgrades |
| `id` | no | derived from tool, rule and location when omitted |
