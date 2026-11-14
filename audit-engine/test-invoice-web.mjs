import fs from 'node:fs';
import crypto from 'node:crypto';
import {evaluateInvoice} from './invoice-web-core.mjs';
const chunks=[];for await(const chunk of process.stdin)chunks.push(chunk);const text=Buffer.concat(chunks).toString('utf8');
const request=JSON.parse(text),hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const result=await evaluateInvoice(request.cut,request.policy,request.reference??null,request.source_hash??null,request.reference_hash??null,hash);
process.stdout.write(JSON.stringify(result));
