var { exec } = require("child_process");

/**
 * Intentionally vulnerable: shells out with unsanitized user input.
 */
function pingHost(host) {
  // command injection: host is concatenated into a shell command
  return new Promise(function (resolve, reject) {
    exec("ping -c 1 " + host, function (err, stdout, stderr) {
      if (err) return reject(err);
      resolve(stdout || stderr);
    });
  });
}

module.exports = { pingHost };
