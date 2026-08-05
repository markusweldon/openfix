var crypto = require("crypto");

/**
 * Intentionally vulnerable: deprecated createCipher (password-based, weak).
 * File path avoids policy sensitive segments (auth/crypto/secret).
 */
function encryptNote(plaintext) {
  var legacy = crypto.createCipher("aes-128-cbc", "password");
  var enc = legacy.update(plaintext, "utf8", "hex");
  enc += legacy.final("hex");
  return enc;
}

module.exports = { encryptNote };
