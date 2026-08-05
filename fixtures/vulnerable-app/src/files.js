var fs = require("fs");
var path = require("path");

/**
 * Intentionally vulnerable: joins user input onto a base directory
 * without rejecting path traversal sequences.
 */
function readUserFile(userPath) {
  var base = path.join(__dirname, "..", "data");
  var target = path.join(base, userPath);
  return fs.readFileSync(target, "utf8");
}

module.exports = { readUserFile };
