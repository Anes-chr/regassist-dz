// Pilote DevTools minimal (Edge/Chrome sans fenêtre) pour les tests de l'interface : aucune dépendance npm (WebSocket et fetch natifs de Node).
import { spawn, spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import net from 'node:net';
import path from 'node:path';

function findBrowser() {
  if (process.env.BROWSER_PATH && fs.existsSync(process.env.BROWSER_PATH)) return process.env.BROWSER_PATH;
  if (process.platform !== 'win32') {
    for (const cmd of ['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium']) {
      try {
        const res = spawnSync('which', [cmd], { encoding: 'utf-8' });
        if (res.status === 0 && res.stdout.trim() && fs.existsSync(res.stdout.trim())) {
          return res.stdout.trim();
        }
      } catch {}
    }
  }
  const CANDIDATES = [
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium-browser', '/usr/bin/chromium',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
  ];
  return CANDIDATES.find((p) => fs.existsSync(p));
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const within = (p, ms, what) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('Délai dépassé : ' + what)), ms))]);
const freePort = () => new Promise((res) => { const s = net.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); }); });

export async function startBrowser() {
  const exe = findBrowser();
  assert.ok(exe, 'Aucun navigateur Edge/Chrome trouvé');

  let target, proc, profile, wsUrl, lastError = '';
  for (let attempt = 0; attempt < 3 && !target; attempt++) {
    profile = fs.mkdtempSync(path.join(os.tmpdir(), 'local_app_ui_'));
    const port = await freePort();
    const flags = [
      '--headless=new', '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
      '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
      '--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1', `--user-data-dir=${profile}`,
      `--remote-debugging-port=${port}`, '--remote-allow-origins=*', '--window-size=1360,900', 'about:blank'
    ];
    let stderr = '';
    proc = spawn(exe, flags, { stdio: ['ignore', 'ignore', 'pipe'] });
    if (proc.stderr) proc.stderr.on('data', (d) => { stderr += d.toString(); });
    for (let i = 0; i < 60 && !target; i++) {
      if (proc.exitCode !== null) {
        lastError = `le processus s'est arrêté avec code ${proc.exitCode} : ${stderr}`;
        break;
      }
      await sleep(200);
      try {
        const res = await fetch(`http://127.0.0.1:${port}/json/list`);
        const l = await res.json();
        target = l.find((t) => t.type === 'page') || l[0];
        if (target && target.webSocketDebuggerUrl) {
          wsUrl = target.webSocketDebuggerUrl;
          break;
        }
      } catch (e) {
        lastError = e.message;
      }
    }
    if (!target) {
      try {
        if (process.platform === 'win32') {
          spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { stdio: 'ignore' });
        } else {
          proc.kill('SIGKILL');
        }
      } catch {}
      try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
    }
  }
  assert.ok(target && wsUrl, 'Le navigateur de test ne répond pas : ' + lastError);
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('WebSocket DevTools')); });

  let nextId = 0;
  const pending = new Map(), listeners = [];
  const B = { requests: [], violations: [], exceptions: [] };
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { const p = pending.get(msg.id); pending.delete(msg.id); msg.error ? p.rej(new Error(msg.error.message)) : p.res(msg.result); return; }
    for (const l of [...listeners]) l(msg);
    if (msg.method === 'Network.requestWillBeSent') B.requests.push(msg.params.request.url);
    if (msg.method === 'Runtime.exceptionThrown') B.exceptions.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
    if (msg.method === 'Log.entryAdded' && msg.params.entry.source !== 'network' && /Content Security Policy|Refused to/i.test(msg.params.entry.text)) B.violations.push(msg.params.entry.text);
  };
  B.send = (method, params = {}) => new Promise((res, rej) => { const id = ++nextId; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
  const waitEvent = (name) => new Promise((res) => { const l = (m) => { if (m.method === name) { listeners.splice(listeners.indexOf(l), 1); res(m.params); } }; listeners.push(l); });
  B.ev = async (expression) => {
    const r = await B.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error('JS: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result.value;
  };
  B.waitFor = async (expression, what, timeout = 20000) => {
    const t0 = Date.now(); let last;
    while (Date.now() - t0 < timeout) { try { last = await B.ev(expression); if (last) return last; } catch (e) { last = e.message; } await sleep(100); }
    throw new Error('Délai dépassé : ' + what + ' (dernière valeur : ' + JSON.stringify(last) + ')');
  };
  B.nav = async (url) => { const loaded = waitEvent('Page.loadEventFired'); await B.send('Page.navigate', { url }); await within(loaded, 20000, 'chargement de ' + url); };
  B.fresh = async (url) => {                       // page neuve, historique vide, vérification de disponibilité du service terminée (l'état n'est plus affiché : on attend la réponse de /api/status)
    await B.nav(url); await B.ev('localStorage.clear()'); await B.nav(url);
    await B.waitFor(`performance.getEntriesByType('resource').some((e) => e.name.endsWith('/api/status')) || !!document.getElementById('composer-msg').textContent`, 'vérification de disponibilité');
    await sleep(80);
  };
  B.text = (sel) => B.ev(`(document.querySelector(${JSON.stringify(sel)}) || {textContent: null}).textContent`);
  B.count = (sel) => B.ev(`document.querySelectorAll(${JSON.stringify(sel)}).length`);
  B.exists = (sel) => B.ev(`!!document.querySelector(${JSON.stringify(sel)})`);
  B.ask = (q) => B.ev(`(() => { const t = document.getElementById('question'); t.value = ${JSON.stringify(q)}; t.dispatchEvent(new Event('input', { bubbles: true })); document.getElementById('form').requestSubmit(); })()`);
  B.close = () => {
    try { ws.close(); } catch (e) { /* ignoré */ }
    if (process.platform === 'win32') {
      try { spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { stdio: 'ignore' }); } catch {}
    } else {
      try { proc.kill('SIGKILL'); } catch {}
    }
    setTimeout(() => { try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) { /* profil temporaire : sans importance */ } }, 1500).unref();
  };
  for (const d of ['Page', 'Runtime', 'Network', 'Log']) await B.send(d + '.enable');
  return B;
}
