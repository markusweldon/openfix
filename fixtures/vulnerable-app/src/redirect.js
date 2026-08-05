/**
 * Intentionally vulnerable: open redirect — trusts user-supplied URL.
 */
function nextUrl(raw) {
  // no allowlist; attacker can send https://evil.example
  return raw || "/";
}

module.exports = { nextUrl };
