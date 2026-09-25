import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
async function text(n){return readFile(new URL(`../prompts/${n}`,import.meta.url),'utf8')}
test('scout prompt has identity, quality markers, path and ownership',async()=>{const s=await text('iran-stock-scout.md'); for(const x of ['Prompt-Version: 1.0','YYYY-MM-DD-IR-TSE-1200','DATA_NOT_VERIFIED','DATA_CONFLICT','reports/iran-stocks/YYYY-MM-DD/scout.json','must never write auditor.json']) assert.match(s,new RegExp(x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i'));});
test('auditor prompt has identity, scout comparison, paths and ownership',async()=>{const s=await text('iran-stock-auditor.md'); for(const x of ['Prompt-Version: 1.0','YYYY-MM-DD-IR-TSE-1200','DATA_NOT_VERIFIED','DATA_CONFLICT','CONFIRMED','REJECTED','reports/iran-stocks/YYYY-MM-DD/auditor.json','reports/iran-stocks/YYYY-MM-DD/final.json','must never overwrite scout.json']) assert.match(s,new RegExp(x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i'));});
