import { readFile } from 'node:fs/promises';
const map={scout:'scout-report.schema.json',auditor:'auditor-report.schema.json',final:'final-report.schema.json',fundamental:'fundamental-state.schema.json'};
export async function loadSchema(kind){
  const f=map[kind]; if(!f) throw new Error(`Unknown schema kind: ${kind}`);
  return JSON.parse(await readFile(new URL(`../../schemas/${f}`, import.meta.url),'utf8'));
}
