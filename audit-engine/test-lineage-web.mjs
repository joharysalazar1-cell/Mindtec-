import {evaluateLineage} from './lineage-web-core.mjs';
const chunks=[];for await(const c of process.stdin)chunks.push(c);const data=JSON.parse(Buffer.concat(chunks).toString('utf8'));process.stdout.write(JSON.stringify(evaluateLineage(data.bundle,data.invoice,data.scan)));
