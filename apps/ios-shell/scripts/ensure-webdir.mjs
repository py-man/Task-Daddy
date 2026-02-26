import { mkdirSync, existsSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

const target = "www/index.html";

if (!existsSync("www")) {
  mkdirSync("www", { recursive: true });
}

if (!existsSync(target)) {
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(
    target,
    `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Task-Daddy iOS Shell</title>
    <style>
      html, body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0a0f1f; color: #d6e0ff; }
      .wrap { padding: 24px; }
      .card { border: 1px solid rgba(255,255,255,.15); border-radius: 16px; background: rgba(255,255,255,.06); padding: 16px; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <h2>Task-Daddy iOS Shell</h2>
        <p>Web assets placeholder generated automatically by ios-shell.</p>
      </div>
    </div>
  </body>
</html>
`
  );
  console.log("Created www/index.html");
}

