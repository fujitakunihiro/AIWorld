import type { Resident } from './village';
export function rememberResident(resident: Resident, text: string) {
  const memory = text.slice(0, 500);
  const duplicate = resident.memories.indexOf(memory);
  if (duplicate >= 0) resident.memories.splice(duplicate, 1);
  resident.memories.push(memory);
  if (resident.memories.length > 8) {
    const old = resident.memories.shift()!;
    // Keep several older experiences, deduplicate frequent work, and cap context.
    const parts = resident.memorySummary.replace(/^以前の記憶：/, '').split(' ／ ').filter(Boolean);
    if (!parts.includes(old)) parts.push(old);
    while (parts.join(' ／ ').length > 480 && parts.length > 1) parts.shift();
    resident.memorySummary = `以前の記憶：${parts.join(' ／ ').slice(-480)}`;
  }
}
