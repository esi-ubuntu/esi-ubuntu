import test from 'node:test'; import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, access } from 'node:fs/promises'; import os from 'node:os'; import path from 'node:path';
import { prepareUiData } from '../scripts/prepare-ui-data.mjs';
test('rebuilds indexes, copies valid report assets, and removes stale output', async()=>{
 const tmp=await mkdtemp(path.join(os.tmpdir(),'mih-')); const out=path.join(tmp,'public','data');
 await import('node:fs/promises').then(fs=>fs.mkdir(out,{recursive:true})); await writeFile(path.join(out,'stale.txt'),'stale');
 await prepareUiData({reportRoot:new URL('../fixtures/reports/',import.meta.url).pathname,outDir:out});
 await assert.rejects(access(path.join(out,'stale.txt')));
 const idx=JSON.parse(await readFile(path.join(out,'report-index.json'),'utf8')); assert.equal(idx.latest_valid_final.date,'2026-09-25');
 const copied=JSON.parse(await readFile(path.join(out,'reports','2026-09-25','final.json'),'utf8')); assert.equal(copied.report_id,'2026-09-25-IR-TSE-1200');
});
