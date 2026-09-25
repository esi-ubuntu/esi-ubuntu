import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const files={scout:'schemas/scout-report.schema.json',auditor:'schemas/auditor-report.schema.json',final:'schemas/final-report.schema.json',fundamental:'schemas/fundamental-state.schema.json'};
for(const [kind,file] of Object.entries(files)){test(`${kind} schema exists and is version 1.0`,async()=>{const value=JSON.parse(await readFile(new URL(`../${file}`,import.meta.url),'utf8'));assert.equal(value['x-schema-version'],'1.0');assert.ok(value.$id);});}
test('scout schema requires report identity and constrains report id',async()=>{const s=JSON.parse(await readFile(new URL('../schemas/scout-report.schema.json',import.meta.url),'utf8'));assert.ok(s.required.includes('report_id'));assert.ok(s.required.includes('market'));assert.equal(s.properties.report_id.pattern,'^\\d{4}-\\d{2}-\\d{2}-IR-TSE-1200$');});
test('score definition is constrained to 0..100',async()=>{const c=JSON.parse(await readFile(new URL('../schemas/common.schema.json',import.meta.url),'utf8'));assert.equal(c.$defs.score.minimum,0);assert.equal(c.$defs.score.maximum,100);});
