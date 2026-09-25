import test from 'node:test';
import assert from 'node:assert/strict';
import { buildReportIndex, buildSymbolHistory } from '../scripts/build-index.mjs';
const root=new URL('../fixtures/reports/', import.meta.url).pathname;
test('report index orders days and tolerates scout-only day', async()=>{ const x=await buildReportIndex(root); assert.deepEqual(x.reports.map(r=>r.date),['2026-09-24','2026-09-25']); assert.equal(x.reports[0].scout_available,true); assert.equal(x.reports[0].final_available,false); assert.equal(x.reports[1].final_available,true); assert.equal(x.latest_valid_final.date,'2026-09-25'); });
test('symbol history spans multiple days', async()=>{ const h=await buildSymbolHistory(root); assert.equal(h.FMLI.length,2); assert.equal(h.FMLI[0].date,'2026-09-24'); assert.equal(h.FMLI[1].date,'2026-09-25'); });
