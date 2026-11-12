#!/usr/bin/env node
/**
 * Serve build/ the way GitHub Pages does (no dependencies), for local checks.
 *
 *   npm run serve:pages -- [--port 4173]
 *
 * `docusaurus serve` resolves /docs to static/docs/index.html (a redirect
 * stub for /docs/), which then loops. GitHub Pages serves docs.html for /docs
 * and docs/index.html only for /docs/. This mimics that order:
 *   /a/b  -> a/b (file), a/b.html, a/b/index.html
 *   /a/b/ -> a/b/index.html
 * Unknown paths get 404.html with status 404.
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

const here = path.dirname(url.fileURLToPath(import.meta.url));
const BUILD = path.resolve(here, '..', 'build');
const BASE = '/inventag-aws/';
const i = process.argv.indexOf('--port');
const PORT = Number(i > -1 ? process.argv[i + 1] : 4173);
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon',
  '.woff2': 'font/woff2', '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8',
  '.webmanifest': 'application/manifest+json', '.yaml': 'text/yaml', '.yml': 'text/yaml',
};

function resolve(p) {
  const rel = decodeURIComponent(p.slice(BASE.length));
  const cands = p.endsWith('/') ? [path.join(rel, 'index.html')] : [rel, `${rel}.html`, path.join(rel, 'index.html')];
  for (const c of cands) {
    const f = path.join(BUILD, c);
    if (!f.startsWith(BUILD)) return null;
    if (fs.existsSync(f) && fs.statSync(f).isFile()) return f;
  }
  return null;
}

http
  .createServer((req, res) => {
    const p = new URL(req.url, 'http://x').pathname;
    if (p === '/inventag-aws') {
      res.writeHead(301, {Location: BASE}).end();
      return;
    }
    const f = p.startsWith(BASE) ? resolve(p) : null;
    const file = f || path.join(BUILD, '404.html');
    res.writeHead(f ? 200 : 404, {'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream'});
    fs.createReadStream(file).pipe(res);
  })
  .listen(PORT, () => console.log(`Serving ${BUILD} at http://localhost:${PORT}${BASE}`));
