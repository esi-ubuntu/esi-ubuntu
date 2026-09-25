import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { validateDocument } from './validation.mjs';
export async function loadReport(file,kind){
 try{ const value=JSON.parse(await readFile(file,'utf8')); const v=validateDocument(kind,value); return v.valid?{valid:true,value}:{valid:false,errors:v.errors}; }
 catch(e){ return {valid:false,errors:[e.message]}; }
}
export function kindFromName(file){ const n=path.basename(file); return n==='scout.json'?'scout':n==='auditor.json'?'auditor':n==='final.json'?'final':null; }
