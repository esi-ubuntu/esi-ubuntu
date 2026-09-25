#!/usr/bin/env node
import { readdir, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { loadReport } from './lib/report-loader.mjs';
async function dayDirs(root){ try{return (await readdir(root,{withFileTypes:true})).filter(e=>e.isDirectory()&&/^\d{4}-\d{2}-\d{2}$/.test(e.name)).map(e=>e.name).sort();}catch{return [];} }
export async function buildReportIndex(root='reports/iran-stocks'){
 const reports=[]; let latest=null;
 for(const date of await dayDirs(root)){
  const row={date,report_id:`${date}-IR-TSE-1200`,scout_available:false,audit_available:false,final_available:false,scout_path:null,auditor_path:null,final_path:null};
  for(const [name,kind,key] of [['scout.json','scout','scout'],['auditor.json','auditor','audit'],['final.json','final','final']]){
   const file=path.join(root,date,name); const r=await loadReport(file,kind); if(r.valid){row[`${key}_available`]=true; row[`${kind==='auditor'?'auditor':kind}_path`]=file; if(kind==='final') latest={date,report_id:r.value.report_id,path:file};}
  }
  reports.push(row);
 }
 return {schema_version:'1.0',market:'iran_stock',reports,latest_valid_final:latest};
}
function candidatesOf(day){ return day.final?.prime_candidates ?? day.auditor?.finalists ?? day.scout?.candidates ?? []; }
export async function buildSymbolHistory(root='reports/iran-stocks'){
 const history={};
 for(const date of await dayDirs(root)){
  const day={};
  for(const [name,kind] of [['scout.json','scout'],['auditor.json','auditor'],['final.json','final']]){const r=await loadReport(path.join(root,date,name),kind); if(r.valid) day[kind]=r.value;}
  for(const c of candidatesOf(day)){
   (history[c.symbol]??=[]).push({date,report_id:`${date}-IR-TSE-1200`,core_fundamental_score:c.core_fundamental_score,daily_valuation_score:c.daily_valuation_score??null,technical_score:c.technical_score,tape_score:c.tape_score,news_score:c.news_score,daily_opportunity_score:c.daily_opportunity_score??null,label:c.label,final_available:Boolean(day.final),audit_available:Boolean(day.auditor)});
  }
 }
 return history;
}
async function main(){ const root=process.argv[2]??'reports/iran-stocks'; const out=process.argv[3]??'generated'; await mkdir(out,{recursive:true}); await writeFile(path.join(out,'report-index.json'),JSON.stringify(await buildReportIndex(root),null,2)+'\n'); await writeFile(path.join(out,'symbol-history.json'),JSON.stringify(await buildSymbolHistory(root),null,2)+'\n'); }
if(import.meta.url===`file://${process.argv[1]}`) main();
