import { DatabaseSync } from 'node:sqlite';
const output = process.argv[2];
if (!output || !/^\/data\/world-pre-unreal-[0-9-]+\.sqlite$/.test(output)) throw new Error('Unexpected backup path');
const db = new DatabaseSync('/data/world.sqlite');
db.exec(`VACUUM INTO '${output}'`);
db.close();
console.log(output);
