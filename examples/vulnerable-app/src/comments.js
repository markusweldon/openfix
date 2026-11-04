/**
 * Intentionally vulnerable: reflects HTML from query without encoding (stored XSS-ish).
 */
function renderComment(body) {
  return "<div class=\"comment\">" + body + "</div>";
}

module.exports = { renderComment };
