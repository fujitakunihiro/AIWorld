import { describeCommand, type InstructionRecord, type InstructionResult } from '../../../shared/instructions';
import type { VillageState } from '../../../shared/village';
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
export class InstructionUI {
  onSend: (id: string, text: string) => void = () => {};
  private connected = false;
  private state?: VillageState;
  private pending?: { id: string; text: string; timer: ReturnType<typeof setTimeout> };
  private rows = new Map<string, { element: HTMLElement; jobs: HTMLElement[] }>();
  private dialog = $<HTMLDialogElement>('instructions-dialog');
  constructor() {
    $('open-instructions').onclick = () => { this.dialog.showModal(); $('instruction-text').focus(); };
    $('close-instructions').onclick = () => this.dialog.close();
    for (const [form, input] of [['quick-instruction', 'quick-instruction-text'], ['instruction-form', 'instruction-text']]) {
      $(form).onsubmit = e => { e.preventDefault(); const field = $<HTMLInputElement | HTMLTextAreaElement>(input); this.send(field.value.trim()); };
    }
    document.querySelectorAll<HTMLButtonElement>('[data-instruction]').forEach(button => button.onclick = () => { $<HTMLTextAreaElement>('instruction-text').value = button.dataset.instruction!; $('instruction-text').focus(); });
    this.dialog.addEventListener('click', e => { if (e.target === this.dialog) { const r = this.dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) this.dialog.close(); } });
  }
  configure(mode: 'llm' | 'rules') { $('instruction-mode').textContent = mode === 'llm' ? '✦ LLM連携' : '✦ ローカル解析'; }
  setConnected(value: boolean) { this.connected = value; this.buttons(); if (!value && this.pending) this.feedback('接続が切れました。再接続後、指示履歴で受付結果を確認します。'); }
  private buttons() { document.querySelectorAll<HTMLButtonElement>('.instruction-send').forEach(b => { b.disabled = !this.connected || !!this.pending; }); }
  private feedback(text: string, failed = false) {
    for (const id of ['instruction-feedback', 'instruction-dialog-feedback']) { $(id).textContent = text; $(id).classList.toggle('instruction-error', failed); }
  }
  private send(text: string) {
    if (!this.connected || this.pending) return;
    if (!text || text.length > 500) { this.feedback('指示は1〜500文字で入力してください。', true); return; }
    // getRandomValues also works over plain HTTP on a home LAN.
    const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
    const id = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    this.pending = { id, text, timer: setTimeout(() => { this.pending = undefined; this.buttons(); this.feedback('受付結果を確認できませんでした。再送する前に指示履歴を確認してください。', true); }, 25_000) };
    this.buttons(); this.feedback('指示を解釈しています…'); this.onSend(id, text);
  }
  result(result: InstructionResult) {
    if (result.id !== this.pending?.id) return;
    clearTimeout(this.pending.timer);
    if (result.ok) for (const id of ['quick-instruction-text', 'instruction-text']) { const field = $<HTMLInputElement | HTMLTextAreaElement>(id); if (field.value.trim() === this.pending.text) field.value = ''; }
    this.pending = undefined; this.buttons(); this.feedback(`${result.message}${result.record ? ` ${result.record.notice}` : ''}`, !result.ok);
  }
  update(state: VillageState, paused: boolean) {
    this.state = state;
    const records = state.instructions.slice(-8).reverse();
    const accepted = records.find(record => record.id === this.pending?.id);
    if (accepted && this.pending) this.result({ type: 'instruction-result', id: accepted.id, ok: true, message: paused ? '指示を保存しました。時間を進めると実行します。' : '指示を保存しました。住民が順に実行します。', record: accepted });
    if (!records.length) return;
    if (!this.rows.size) $('instruction-history').replaceChildren();
    for (const record of records) {
      let row = this.rows.get(record.id);
      if (!row) { row = this.createRow(record); this.rows.set(record.id, row); }
      record.jobs.forEach((job, i) => { const status = { running: paused ? '一時停止中' : '実行中', complete: '完了', superseded: '切替済み' }[job.status]; row!.jobs[i].textContent = `${status} · ${job.detail}`; });
    }
    // Keep details elements mounted so clock updates never close a user's JSON preview.
    records.forEach((record, i) => { const row = this.rows.get(record.id)!.element; const parent = $('instruction-history'); if (parent.children[i] !== row) parent.insertBefore(row, parent.children[i] ?? null); });
    for (const [id, row] of this.rows) if (!records.some(r => r.id === id)) { row.element.remove(); this.rows.delete(id); }
  }
  clock(paused: boolean) { if (this.state) this.update(this.state, paused); }
  private createRow(record: InstructionRecord) {
    const element = document.createElement('article'); element.className = 'instruction-record';
    const title = document.createElement('strong'); title.textContent = record.text; element.append(title);
    const source = document.createElement('small'); source.textContent = `${record.source === 'llm' ? 'LLM' : 'ローカル解析'} · ${record.notice}`; element.append(source);
    const jobs = record.jobs.map(job => { const p = document.createElement('p'); p.title = describeCommand(job.command); element.append(p); return p; });
    const details = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = '変換したJSONを見る'; const pre = document.createElement('pre'); pre.textContent = JSON.stringify({ commands: record.jobs.map(job => job.command) }, null, 2); details.append(summary, pre); element.append(details);
    return { element, jobs };
  }
}
