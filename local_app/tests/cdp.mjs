// Pilote DevTools minimal (Edge/Chrome sans fenêtre) pour les tests de l'interface : aucune dépendance npm (WebSocket et fetch natifs de Node).
import { spawn, spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import net from 'node:net';
import path from 'node:path';

const CANDIDATES = [process.env.BROWSER_PATH, 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'].filter(Boolean);
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const within = (p, ms, what) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('Délai dépassé : ' + what)), ms))]);
const freePort = () => new Promise((res) => { const s = net.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); }); });

export async function startBrowser() {
  const exe = CANDIDATES.find((p) => fs.existsSync(p));
  assert.ok(exe, 'Aucun navigateur Edge/Chrome trouvé');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'local_app_ui_'));
  const port = await freePort();
  // --host-resolver-rules : toute résolution DNS hors 127.0.0.1 échoue (navigateur sans accès Internet) : si les tests passent, l'interface n'a besoin d'aucune ressource externe.
  const proc = spawn(exe, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1', `--user-data-dir=${profile}`,
    `--remote-debugging-port=${port}`, '--remote-allow-origins=*', '--window-size=1360,900', 'about:blank'], { stdio: 'ignore' });
  let target;
  for (let i = 0; i < 100 && !target; i++) {
    await sleep(200);
    try { const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); target = l.find((t) => t.type === 'page'); } catch (e) { /* démarrage */ }
  }
  assert.ok(target, 'Le navigateur de test ne répond pas');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
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
    spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { stdio: 'ignore' });
    setTimeout(() => { try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) { /* profil temporaire : sans importance */ } }, 1500).unref();
  };
  for (const d of ['Page', 'Runtime', 'Network', 'Log']) await B.send(d + '.enable');
  return B;
}
