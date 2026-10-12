import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { Block, SAVE_VERSION, generateWorld, index, type Edit, type WorldSnapshot } from '../../../shared/world';
import { editSchema } from '../../../shared/schema';
import type { VillageState } from '../../../shared/village';
import { villageSchema } from './village-schema';
import { inHut } from '../buildings/hut';
export class WorldStore {
  private db: DatabaseSync;
  readonly base: Uint8Array;
  readonly data: Uint8Array;
  readonly seed: number;
  revision: number;
  time: number;
  speed: number;
  village: VillageState | null = null;
  constructor(path: string, seed: number) {
    if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true });
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS world (id TEXT PRIMARY KEY, version INTEGER NOT NULL, seed INTEGER NOT NULL, revision INTEGER NOT NULL, time REAL NOT NULL, speed INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS edits (x INTEGER, y INTEGER, z INTEGER, block INTEGER NOT NULL, PRIMARY KEY(x,y,z));
      CREATE TABLE IF NOT EXISTS simulation (id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL);`);
    this.db.prepare('INSERT OR IGNORE INTO world VALUES (?, ?, ?, 0, 480, 1)').run('island-1', SAVE_VERSION, seed);
    const row = this.db.prepare('SELECT * FROM world WHERE id=?').get('island-1')!;
    if (![1, 2, 3, 4, SAVE_VERSION].includes(Number(row.version))) { this.db.close(); throw new Error('未対応の保存バージョンです。データを保護するため起動を停止しました。'); }
    this.seed = Number(row.seed); this.revision = Number(row.revision); this.time = Number(row.time); this.speed = Number(row.speed);
    this.base = generateWorld(this.seed); this.data = this.base.slice();
    for (const edit of this.edits()) this.data[index(edit.x, edit.y, edit.z)] = edit.block;
    const saved = this.db.prepare('SELECT state FROM simulation WHERE id=1').get();
    if (saved) {
      try { this.village = villageSchema.parse(JSON.parse(String(saved.state))); }
      catch (error) { this.db.close(); throw new Error('住民の保存データが不正です。データを保護するため起動を停止しました。', { cause: error }); }
    }
    if (row.version !== SAVE_VERSION) {
      if (this.village && Number(row.version) < 4) {
        const event = { id: this.village.nextEvent++, time: this.village.elapsed, kind: 'growth' as const, text: '世界が128×128に広がりました。はじまりの島を残し、新しい森・山・平地を持つ島々が加わりました。' };
        this.village.events.push(event); if (this.village.events.length > 30) this.village.events.shift();
        this.village.chronicle.push(event);
        if (this.village.chronicle.length > 300) { const old = this.village.chronicle.shift()!; this.village.archive.count++; this.village.archive.through = old.time; this.village.archive.kinds[old.kind] = (this.village.archive.kinds[old.kind] ?? 0) + 1; }
      }
      this.db.exec('BEGIN IMMEDIATE');
      try {
        if (this.village) this.db.prepare('INSERT INTO simulation VALUES(1,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state').run(JSON.stringify(this.village));
        this.db.prepare('UPDATE world SET version=? WHERE id=?').run(SAVE_VERSION, 'island-1'); this.db.exec('COMMIT');
      } catch (error) { this.db.exec('ROLLBACK'); this.db.close(); throw error; }
    }
  }
  edits(): Edit[] { return this.db.prepare('SELECT x,y,z,block FROM edits ORDER BY y,z,x').all() as unknown as Edit[]; }
  snapshot(): WorldSnapshot {
    return { type: 'snapshot', id: 'island-1', name: 'はじまりの島', version: SAVE_VERSION, seed: this.seed,
      revision: this.revision, edits: this.edits(), time: this.time, speed: this.speed, village: this.village };
  }
  edit(input: unknown): Edit {
    const { x, y, z, block, expected } = editSchema.parse(input);
    const i = index(x, y, z), current = this.data[i];
    if (current !== expected) throw new Error('別の操作でこのブロックが変わりました。もう一度選んでください。');
    if (y === 0) throw new Error('島の基盤（高さ0）は編集できません。');
    if (this.village?.huts.some(h => inHut({ x, y, z }, h))) throw new Error('住民の建物・畑と建築敷地は保護されています。周りの地形を編集してください。');
    if (this.village?.bridges.some(b => b.blocks.some(e => e.x === x && e.z === z && y >= e.y - 1 && y <= e.y + 2))) throw new Error('橋と建設予定の通路は保護されています。');
    if (this.village?.residents.some(r => Math.floor(r.position.x) === x && Math.floor(r.position.z) === z && y >= r.position.y - 1 && y < r.position.y + 2)) throw new Error('住民の足場や体と重なる位置は編集できません。');
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
  saveVillage(village: VillageState, edits: Edit[] = []) {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const upsert = this.db.prepare('INSERT INTO edits VALUES (?,?,?,?) ON CONFLICT(x,y,z) DO UPDATE SET block=excluded.block');
      const remove = this.db.prepare('DELETE FROM edits WHERE x=? AND y=? AND z=?');
      for (const edit of edits) {
        if (edit.block === this.base[index(edit.x, edit.y, edit.z)]) remove.run(edit.x, edit.y, edit.z);
        else upsert.run(edit.x, edit.y, edit.z, edit.block);
      }
      this.db.prepare('INSERT INTO simulation VALUES(1,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state').run(JSON.stringify(village));
      this.db.prepare('UPDATE world SET time=?,speed=?,revision=? WHERE id=?').run(this.time, this.speed, this.revision + (edits.length ? 1 : 0), 'island-1');
      this.db.exec('COMMIT');
    } catch (error) { this.db.exec('ROLLBACK'); throw error; }
    for (const edit of edits) this.data[index(edit.x, edit.y, edit.z)] = edit.block;
    if (edits.length) this.revision++;
    this.village = village;
  }
  saveClock() { this.db.prepare('UPDATE world SET time=?,speed=? WHERE id=?').run(this.time, this.speed, 'island-1'); }
  close() { if (this.village) this.saveVillage(this.village); else this.saveClock(); this.db.close(); }
}
