import test from 'node:test'; import assert from 'node:assert/strict';
import { validateDocument } from '../scripts/lib/validation.mjs';
import { buildReportIndex } from '../scripts/build-index.mjs';
import { prepareUiData } from '../scripts/prepare-ui-data.mjs';
import { readFile, mkdtemp } from 'node:fs/promises'; import path from 'node:path'; import os from 'node:os';
const root=new URL('../fixtures/reports/',import.meta.url).pathname;
test('Scout -> Auditor -> Final fixture pipeline is valid and indexable',async()=>{
 for(const [d,n,k] of [['2026-09-24','scout','scout'],['2026-09-25','scout','scout'],['2026-09-25','auditor','auditor'],['2026-09-25','final','final']]){const v=JSON.parse(await readFile(path.join(root,d,`${n}.json`),'utf8'));assert.equal(validateDocument(k,v).valid,true);}
 const idx=await buildReportIndex(root); assert.equal(idx.reports.length,2); assert.equal(idx.latest_valid_final.report_id,'2026-09-25-IR-TSE-1200');
 const out=path.join(await mkdtemp(path.join(os.tmpdir(),'mih-e2e-')),'data'); const r=await prepareUiData({reportRoot:root,outDir:out}); assert.equal(r.index.latest_valid_final.date,'2026-09-25');
});
