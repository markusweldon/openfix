/**
 * Intentionally vulnerable: SQL built via string concatenation.
 */
function findUserByName(name) {
  var sql = "SELECT * FROM users WHERE name = '" + name + "'";
  return sql;
}

module.exports = { findUserByName };
