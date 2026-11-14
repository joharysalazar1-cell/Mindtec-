// Local verification utility only; production reader has no Node dependency.
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {openWorkbookZip} from './xlsx-zip.mjs';
const results=[];
for(const path of process.argv.slice(2)){
 const source=new Uint8Array(await readFile(path)),zip=openWorkbookZip(source),parts=[];
 for(const e of zip.parts){const bytes=await zip.read(e.name);parts.push({name:e.name,size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});}
 results.push({source_sha256:createHash('sha256').update(source).digest('hex'),version:zip.version,parts});
}
process.stdout.write(JSON.stringify(results));
