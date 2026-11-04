var http = require("http");

/**
 * Intentionally vulnerable: server-side request forgery — fetches attacker URL.
 */
function fetchUrl(url) {
  return new Promise(function (resolve, reject) {
    http
      .get(url, function (res) {
        var data = "";
        res.on("data", function (chunk) {
          data += chunk;
        });
        res.on("end", function () {
          resolve(data);
        });
      })
      .on("error", reject);
  });
}

module.exports = { fetchUrl };
