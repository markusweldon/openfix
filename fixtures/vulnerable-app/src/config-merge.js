/**
 * Intentionally vulnerable: merges untrusted JSON into a shared config object.
 */
function applyConfig(userJson) {
  var cfg = { admin: false, theme: "light" };
  var parsed = JSON.parse(userJson);
  for (var key in parsed) {
    cfg[key] = parsed[key];
  }
  return cfg;
}

module.exports = { applyConfig };
