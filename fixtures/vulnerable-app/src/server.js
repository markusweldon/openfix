var express = require("express");
var files = require("./files");
var tokens = require("./auth/tokens");
var { pingHost } = require("./exec");
var { nextUrl } = require("./redirect");
var { calculate } = require("./calc");
var { fetchUrl } = require("./fetch");
var { runUserScript } = require("./sandbox");
var { encryptNote } = require("./util/weak-cipher");
var { findUserByName } = require("./db/query");
var { renderComment } = require("./comments");
var { listDir } = require("./listdir");
var { applyConfig } = require("./config-merge");

var app = express();

// Intentionally loose CORS for scanner finding
app.use(function (req, res, next) {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Credentials", "true");
  next();
});

app.get("/", function (req, res) {
  res.send("openfix vulnerable demo");
});

app.get("/echo", function (req, res) {
  var name = req.query.name || "world";
  res.send("<h1>Hello " + name + "</h1>");
});

app.get("/file", function (req, res) {
  try {
    var contents = files.readUserFile(req.query.path);
    res.type("text/plain").send(contents);
  } catch (err) {
    res.status(400).send(String(err.message || err));
  }
});

app.get("/ping", function (req, res) {
  pingHost(req.query.host || "127.0.0.1")
    .then(function (out) {
      res.type("text/plain").send(out);
    })
    .catch(function (err) {
      res.status(400).send(String(err.message || err));
    });
});

app.get("/go", function (req, res) {
  res.redirect(nextUrl(req.query.next));
});

app.get("/calc", function (req, res) {
  try {
    res.json({ result: calculate(req.query.expr || "1+1") });
  } catch (err) {
    res.status(400).send(String(err.message || err));
  }
});

app.get("/proxy", function (req, res) {
  fetchUrl(req.query.url || "http://127.0.0.1:3000/")
    .then(function (body) {
      res.type("text/plain").send(body);
    })
    .catch(function (err) {
      res.status(400).send(String(err.message || err));
    });
});

app.get("/sandbox", function (req, res) {
  try {
    res.json({ result: runUserScript(req.query.code || "1+1") });
  } catch (err) {
    res.status(400).send(String(err.message || err));
  }
});

app.get("/encrypt", function (req, res) {
  res.json({ ciphertext: encryptNote(req.query.text || "note") });
});

app.get("/user", function (req, res) {
  res.type("text/plain").send(findUserByName(req.query.name || "ada"));
});

app.get("/comment", function (req, res) {
  res.send(renderComment(req.query.body || "hi"));
});

app.get("/ls", function (req, res) {
  listDir(req.query.path || ".")
    .then(function (out) {
      res.type("text/plain").send(out);
    })
    .catch(function (err) {
      res.status(400).send(String(err.message || err));
    });
});

app.post("/config", express.text({ type: "*/*" }), function (req, res) {
  try {
    res.json(applyConfig(req.body || "{}"));
  } catch (err) {
    res.status(400).send(String(err.message || err));
  }
});

app.get("/token-hint", function (req, res) {
  res.json({ hasToken: Boolean(tokens.API_TOKEN) });
});

if (require.main === module) {
  app.listen(3000, function () {
    console.log("listening on :3000");
  });
}

module.exports = app;
