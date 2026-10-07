// INTÉGRATION RÉELLE côté navigateur : interface -> API -> agent -> recherche hybride -> reranker -> llama-server -> réponse affichée.
// Aucun faux : l'application visée est le vrai déploiement (variable UI_URL_REAL). Lancé par test_integration.py.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { startBrowser } from './cdp.mjs';

const URL_REAL = process.env.UI_URL_REAL;
const ORIGIN = new URL(URL_REAL).origin;
let B;
before(async () => { B = await startBrowser(); });
after(() => B && B.close());

test('question juridique réelle : sources et réponse affichées, état du système réel, aucune requête externe', { timeout: 400000 }, async () => {
  await B.fresh(URL_REAL);
  assert.equal((await B.text('.badge-edu')).trim(), 'PROJET ÉDUCATIF · NON OFFICIEL');
  assert.equal(await B.text('#composer-msg'), '', 'le service doit être disponible (y compris le service de rédaction) pour ce test : ' + await B.text('#composer-msg'));

  await B.ask("Quel est le plafond d'indemnisation par déposant ?");
  await B.waitFor(`document.getElementById('answer').getAttribute('aria-busy') === 'true'`, 'traitement en cours');
  await B.waitFor(`document.querySelector('#answer .ans-text') || document.querySelector('#answer .callout-error')`, 'réponse du système réel', 300000);
  assert.equal(await B.exists('#answer .callout-error'), false, 'erreur affichée : ' + await B.text('#answer'));

  const answer = await B.text('#answer .ans-text');
  assert.match(answer, /2[.\s ]?000[.\s ]?000|deux millions/i, 'réponse inattendue : ' + answer);
  assert.ok((await B.count('#sources .source')) >= 1, 'au moins une source affichée');
  assert.ok((await B.count('#sources .source.cited')) >= 1, 'au moins une source citée');
  assert.ok((await B.count('#answer .cite')) >= 1, 'citation cliquable');
  const link = await B.ev(`document.querySelector('#sources .source.cited .src-links a').href`);
  assert.match(link, /^https:\/\/www\.bank-of-algeria\.dz\//, 'lien vers le PDF officiel');
  assert.match(await B.text('#answer .disclaimer'), /ne constitue pas un avis juridique/);
  const page = await B.ev('document.body.innerText');
  assert.ok(!/qwen|llama|rerank|hybrid|retriev|PHASE_4|NO-GO|FROZEN|127\.0\.0\.1|OCR_UNCERTAIN|chunk|\bLLM\b|\bms\b|modèle local|moteur|Traçabilité|score|similarit|[A-Z]:\\/i.test(page),
    'détail technique visible sur la vraie page : ' + (/qwen|llama|rerank|hybrid|retriev|PHASE_4|NO-GO|FROZEN|127\.0\.0\.1|OCR_UNCERTAIN|chunk|\bLLM\b|\bms\b|modèle local|moteur|Traçabilité|score|similarit/i.exec(page) || [''])[0]);
  assert.ok(!/\b(ACTIVE|REPLACED|MODIFIED|ABROGATED|HISTORICAL|UNKNOWN)\b/.test(await B.text('#answer')), 'code interne de statut affiché dans la réponse');

  // requêtes du navigateur : uniquement l'application elle-même
  const foreign = B.requests.filter((u) => !(u.startsWith(ORIGIN + '/') || u.startsWith('data:') || u === 'about:blank'));
  assert.deepEqual(foreign, [], 'requêtes hors application : ' + foreign.join(', '));
  assert.deepEqual(B.violations, []); assert.deepEqual(B.exceptions, []);
});

test('question hors corpus réelle : refus affiché comme refus, sans source ni réponse inventée', { timeout: 120000 }, async () => {
  await B.ask('Quelle est la capitale de la France ?');
  await B.waitFor(`document.querySelector('#answer .callout-info')`, 'refus du système réel', 60000);
  assert.match(await B.text('#answer .callout-info'), /Aucune réponse établie/);
  assert.equal(await B.exists('#answer .ans-text'), false);
  assert.equal(await B.count('#sources .source'), 0);
});
