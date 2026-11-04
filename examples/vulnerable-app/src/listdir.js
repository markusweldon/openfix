var { execFile } = require("child_process");

/**
 * Intentionally vulnerable: shell used with user args via execFile + shell:true.
 */
function listDir(userPath) {
  return new Promise(function (resolve, reject) {
    execFile("ls", ["-la", userPath], { shell: true }, function (err, stdout, stderr) {
      if (err) return reject(err);
      resolve(stdout || stderr);
    });
  });
}

module.exports = { listDir };
