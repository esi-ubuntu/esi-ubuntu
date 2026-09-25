import test from 'node:test'; import assert from 'node:assert/strict';
import { selectCurrentReport, reportAssetPath } from './data.mjs';
const idx={reports:[{date:'2026-09-24',scout_available:true,final_available:false,scout_path:'a'},{date:'2026-09-25',scout_available:true,final_available:true,final_path:'b'}],latest_valid_final:{date:'2026-09-25',path:'b'}};
test('selects latest valid final',()=>{assert.deepEqual(selectCurrentReport(idx),{mode:'final',date:'2026-09-25',path:'b'});});
test('falls back to newest scout as provisional when no final exists',()=>{const x={reports:[{date:'2026-09-24',scout_available:true,final_available:false,scout_path:'a'}],latest_valid_final:null};assert.deepEqual(selectCurrentReport(x),{mode:'provisional',date:'2026-09-24',path:'a'});});
test('maps production report index path to prepared static asset path',()=>{assert.equal(reportAssetPath({date:'2026-09-25',path:'reports/iran-stocks/2026-09-25/final.json'}),'reports/2026-09-25/final.json');});
