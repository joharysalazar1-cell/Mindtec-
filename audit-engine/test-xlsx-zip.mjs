import assert from 'node:assert/strict';
import {test} from 'node:test';
import {deflateRawSync} from 'node:zlib';
import {openWorkbookZip,crc32} from './xlsx-zip.mjs';
const encoder=new TextEncoder();
function archive({names=['xl/workbook.xml'],text='<workbook/>',method=8,descriptor=false,signed=true}={}){
 const local=[],central=[];let offset=0;
 for(const name of names){
  const n=encoder.encode(name),body=encoder.encode(text),data=method===8?deflateRawSync(body):body,crc=crc32(body),flags=descriptor?8:0;
  const l=new Uint8Array(30+n.length+data.length+(descriptor?(signed?16:12):0)),v=new DataView(l.buffer);v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,flags,true);v.setUint16(8,method,true);
  if(!descriptor){v.setUint32(14,crc,true);v.setUint32(18,data.length,true);v.setUint32(22,body.length,true);}v.setUint16(26,n.length,true);l.set(n,30);l.set(data,30+n.length);
  if(descriptor){let p=30+n.length+data.length;if(signed){v.setUint32(p,0x08074b50,true);p+=4;}v.setUint32(p,crc,true);v.setUint32(p+4,data.length,true);v.setUint32(p+8,body.length,true);}
  const c=new Uint8Array(46+n.length),w=new DataView(c.buffer);w.setUint32(0,0x02014b50,true);w.setUint16(6,20,true);w.setUint16(8,flags,true);w.setUint16(10,method,true);w.setUint32(16,crc,true);w.setUint32(20,data.length,true);w.setUint32(24,body.length,true);w.setUint16(28,n.length,true);w.setUint32(42,offset,true);c.set(n,46);local.push(l);central.push(c);offset+=l.length;
 }
 const cs=central.reduce((n,c)=>n+c.length,0),out=new Uint8Array(offset+cs+22);let p=0;for(const chunk of [...local,...central]){out.set(chunk,p);p+=chunk.length;}const v=new DataView(out.buffer);v.setUint32(p,0x06054b50,true);v.setUint16(p+8,names.length,true);v.setUint16(p+10,names.length,true);v.setUint32(p+12,cs,true);v.setUint32(p+16,offset,true);return out;
}
function centralOffset(b){return new DataView(b.buffer).getUint32(b.length-6,true);}
test('CRC known vector',()=>assert.equal(crc32(encoder.encode('123456789')),0xcbf43926));
for(const method of [0,8])for(const descriptor of [false,true])for(const signed of [false,true])test(`read method ${method}, descriptor ${descriptor}, signed ${signed}`,async()=>{
 const z=openWorkbookZip(archive({method,descriptor,signed}));assert.equal(new TextDecoder().decode(await z.read('xl/workbook.xml')),'<workbook/>');assert.equal(z.parts.length,1);
});
test('duplicate and unsafe paths rejected',()=>{for(const names of [['a','a'],['../a'],['/a'],['a\\b'],['a//b'],['a/./b'],['C:a']])assert.throws(()=>openWorkbookZip(archive({names})));});
test('truncated and trailing bytes rejected',()=>{const b=archive();assert.throws(()=>openWorkbookZip(b.subarray(0,b.length-1)));const extra=new Uint8Array(b.length+1);extra.set(b);assert.throws(()=>openWorkbookZip(extra));});
test('local name mismatch rejected',()=>{const b=archive();b[30]=65;assert.throws(()=>openWorkbookZip(b),/mismatch/);});
test('encryption and unknown flags rejected',()=>{for(const flags of [1,64,0x2000]){const b=archive(),v=new DataView(b.buffer);v.setUint16(centralOffset(b)+8,flags,true);assert.throws(()=>openWorkbookZip(b),/unsupported/);}});
test('ZIP64 and multidisk rejected',()=>{for(const field of ['zip64','disk']){const b=archive(),v=new DataView(b.buffer);if(field==='zip64')v.setUint32(centralOffset(b)+42,0xffffffff,true);else v.setUint16(b.length-18,1,true);assert.throws(()=>openWorkbookZip(b));}});
test('part size bound enforced before inflate',()=>{const b=archive(),v=new DataView(b.buffer);v.setUint32(centralOffset(b)+24,100000001,true);assert.throws(()=>openWorkbookZip(b),/size/);});
test('overlapping offsets rejected',()=>{const b=archive({names:['a','b']}),v=new DataView(b.buffer);v.setUint32(centralOffset(b)+47+42,0,true);assert.throws(()=>openWorkbookZip(b),/overlapping/);});
test('stored corruption fails CRC',async()=>{const b=archive({method:0});b[30+'xl/workbook.xml'.length]^=1;await assert.rejects(openWorkbookZip(b).read('xl/workbook.xml'),/CRC/);});
test('declared expansion smaller than actual is stopped',async()=>{const b=archive({text:'a'.repeat(500000)}),v=new DataView(b.buffer);v.setUint32(22,1,true);v.setUint32(centralOffset(b)+24,1,true);await assert.rejects(openWorkbookZip(b).read('xl/workbook.xml'),/expansion/);});
test('bad descriptor rejected',()=>{const b=archive({descriptor:true});b[centralOffset(b)-1]^=1;assert.throws(()=>openWorkbookZip(b),/descriptor/);});
test('caller mutation cannot change checked bytes',async()=>{const b=archive({method:0}),z=openWorkbookZip(b);b.fill(0);assert.equal(new TextDecoder().decode(await z.read('xl/workbook.xml')),'<workbook/>');});
test('missing part rejected',async()=>{await assert.rejects(openWorkbookZip(archive()).read('missing'),/missing/);});
