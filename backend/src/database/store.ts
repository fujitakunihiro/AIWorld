import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { Block, SAVE_VERSION, generateWorld, index, type Edit, type WorldSnapshot } from '../../../shared/world';
import { editSchema } from '../../../shared/schema';
export class WorldStore {
  private db: DatabaseSync;
  readonly base: Uint8Array;
  readonly data: Uint8Array;
  readonly seed: number;
  revision: number;
  time: number;
  speed: number;
  constructor(path: string, seed: number) {
    if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true });
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS world (id TEXT PRIMARY KEY, version INTEGER NOT NULL, seed INTEGER NOT NULL, revision INTEGER NOT NULL, time REAL NOT NULL, speed INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS edits (x INTEGER, y INTEGER, z INTEGER, block INTEGER NOT NULL, PRIMARY KEY(x,y,z));`);
    this.db.prepare('INSERT OR IGNORE INTO world VALUES (?, ?, ?, 0, 480, 1)').run('island-1', SAVE_VERSION, seed);
    const row = this.db.prepare('SELECT * FROM world WHERE id=?').get('island-1')!;
    if (row.version !== SAVE_VERSION) { this.db.close(); throw new Error('未対応の保存バージョンです。データを保護するため起動を停止しました。'); }
    this.seed = Number(row.seed); this.revision = Number(row.revision); this.time = Number(row.time); this.speed = Number(row.speed);
    this.base = generateWorld(this.seed); this.data = this.base.slice();
    for (const edit of this.edits()) this.data[index(edit.x, edit.y, edit.z)] = edit.block;
  }
  edits(): Edit[] { return this.db.prepare('SELECT x,y,z,block FROM edits ORDER BY y,z,x').all() as unknown as Edit[]; }
  snapshot(): WorldSnapshot {
    return { type: 'snapshot', id: 'island-1', name: 'はじまりの島', version: SAVE_VERSION, seed: this.seed,
      revision: this.revision, edits: this.edits(), time: this.time, speed: this.speed };
  }
  edit(input: unknown): Edit {
    const { x, y, z, block, expected } = editSchema.parse(input);
    const i = index(x, y, z), current = this.data[i];
    if (current !== expected) throw new Error('別の操作でこのブロックが変わりました。もう一度選んでください。');
    if (y === 0) throw new Error('島の基盤（高さ0）は編集できません。');
    if (block === current) throw new Error('同じブロックです。');
    const restoringWater = block === Block.Water && this.base[i] === Block.Water;
    if (block === Block.Water && !restoringWater) throw new Error('水は元の水域でのみ復元できます。');
    if (block !== Block.Air && current !== Block.Air && current !== Block.Water && !restoringWater) throw new Error('配置先が空いていません。');
    if (block === Block.Air && (current === Block.Air || current === Block.Water)) throw new Error('削除する固体ブロックがありません。');
    this.db.exec('BEGIN IMMEDIATE');
    try {
      if (block === this.base[i]) this.db.prepare('DELETE FROM edits WHERE x=? AND y=? AND z=?').run(x, y, z);
      else this.db.prepare('INSERT INTO edits VALUES (?,?,?,?) ON CONFLICT(x,y,z) DO UPDATE SET block=excluded.block').run(x, y, z, block);
      this.db.prepare('UPDATE world SET revision=revision+1 WHERE id=?').run('island-1');
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
    this.data[i] = block; this.revision++;
    return { x, y, z, block };
  }
  saveClock() { this.db.prepare('UPDATE world SET time=?,speed=? WHERE id=?').run(this.time, this.speed, 'island-1'); }
  close() { this.saveClock(); this.db.close(); }
}
