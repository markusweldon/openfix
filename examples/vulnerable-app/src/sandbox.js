var vm = require("vm");

/**
 * Intentionally vulnerable: executes attacker-controlled code in a VM context.
 */
function runUserScript(code) {
  return vm.runInNewContext(code, { console: console });
}

module.exports = { runUserScript };
