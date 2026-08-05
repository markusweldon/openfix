/**
 * Intentionally vulnerable: evaluates user-controlled expression.
 */
function calculate(expr) {
  // code injection via eval
  return eval(expr);
}

module.exports = { calculate };
