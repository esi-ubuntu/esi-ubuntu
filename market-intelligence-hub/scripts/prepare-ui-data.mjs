#!/usr/bin/env node
import { rm, mkdir, writeFile, cp } from 'node:fs/promises';
import path from 'node:path';
import { buildReportIndex, buildSymbolHistory } from './build-index.mjs';
import { loadReport } from './lib/report-loader.mjs';
export async function prepareUiData({reportRoot='reports/iran-stocks',outDir='ui/public/data'}={}){
  await rm(outDir,{recursive:true,force:true}); await mkdir(path.join(outDir,'reports'),{recursive:true});
  const index=await buildReportIndex(reportRoot); const history=await buildSymbolHistory(reportRoot);
  await writeFile(path.join(outDir,'report-index.json'),JSON.stringify(index,null,2)+'\n');
  await writeFile(path.join(outDir,'symbol-history.json'),JSON.stringify(history,null,2)+'\n');
  for(const row of index.reports){
    const dest=path.join(outDir,'reports',row.date); await mkdir(dest,{recursive:true});
    for(const [p,kind,name] of [[row.scout_path,'scout','scout.json'],[row.auditor_path,'auditor','auditor.json'],[row.final_path,'final','final.json']]){
      if(!p) continue; const r=await loadReport(p,kind); if(r.valid) await cp(p,path.join(dest,name));
    }
  }
  return {index,history};
}
if(import.meta.url===`file://${process.argv[1]}`) await prepareUiData();
