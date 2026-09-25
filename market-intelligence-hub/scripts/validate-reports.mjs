#!/usr/bin/env node
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { validateDocument } from './lib/validation.mjs';
const explicit=process.argv.slice(2);
async function walk(p){ const out=[]; try{ for(const e of await readdir(p,{withFileTypes:true})){ const f=path.join(p,e.name); if(e.isDirectory()) out.push(...await walk(f)); else if(e.name.endsWith('.json')) out.push(f); } }catch{} return out; }
let files=explicit.length?explicit:[...await walk('reports'),...await walk('state/fundamentals')];
let bad=0;
for(const file of files){
 try{
  const value=JSON.parse(await readFile(file,'utf8'));
  const base=path.basename(file); const kind=base==='scout.json'?'scout':base==='auditor.json'?'auditor':base==='final.json'?'final':file.includes('fundamentals')?'fundamental':null;
  if(!kind) continue;
  const r=validateDocument(kind,value); if(!r.valid){bad++; console.error(`${file}: ${r.errors.join('; ')}`);} else console.log(`${file}: OK`);
 }catch(e){ bad++; console.error(`${file}: ${e.message}`); }
}
process.exitCode=bad?1:0;
