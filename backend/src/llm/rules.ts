import { interpretationSchema } from '../../../shared/instruction-schema';
import type { InstructionCommand } from '../../../shared/instructions';
const help = '「小屋を1軒建てて」「ミオに木材を集めてほしい」「みんな休んで」「自律行動に戻って」のように入力してください。';
export function parseRules(input: string): InstructionCommand[] {
  const text = input.normalize('NFKC').trim();
  if (!text || text.length > 500) throw new Error('指示は1〜500文字で入力してください。');
  // Never turn a negative, unsupported or conditional instruction into its opposite.
  if (/ない|なく|やめ|止め|中止|禁止|キャンセル|もし|場合|以外|より|ではなく|don't|not\b/i.test(text)) throw new Error(`否定・条件・取り消しの指示はまだ解析できません。自律行動への復帰は「自律行動に戻って」と入力してください。`);
  if (/畑|農場|倉庫|城|塔|橋|道路|山|海|砂浜|座標|北|南|東|西|掘って|破壊|削除|壊|戦|コード|実行|API|キー|秘密|warehouse|farm|castle/i.test(text)) throw new Error('このフェーズの建築は村・川・森の近くの小屋に対応しています。採集・休息・自律行動への復帰も指示できます。');
  const clauses = text.split(/[。\n;；]|そして|それから/).map(s => s.trim()).filter(Boolean);
  if (clauses.length > 5) throw new Error('一度の指示は5つまでです。');
  const commands = clauses.map((clause): InstructionCommand => {
    const named = (['ハル', 'ミオ', 'レン', 'ソラ', 'ユイ'] as const).map((name, i) => ({ name, id: ['haru', 'mio', 'ren', 'sora', 'yui'][i] as 'haru' | 'mio' | 'ren' | 'sora' | 'yui' })).filter(p => clause.includes(p.name) || new RegExp(`\\b${p.id}\\b`, 'i').test(clause));
    if (named.length > 1) throw new Error('住民は1人ずつ、または「みんな」で指示してください。');
    const target = named[0]?.id ?? 'all';
    const subject = clause.match(/^([ァ-ヶーA-Za-z]+)(?:に|は|を)/)?.[1];
    if (subject && !named.length && !/^(?:みんな|all)$/i.test(subject)) throw new Error('この村の住民はハル・ミオ・レン・ソラ・ユイです。1人ずつ、または「みんな」で指示してください。');
    const auto = /自律|自由|おまかせ|お任せ|通常|auto/i.test(clause);
    const rest = /休ん|休ませ|休息|休憩|rest/i.test(clause);
    const build = /(?:小屋|家|村).*(?:建|作|つく|追加)|(?:建|作|つく|追加).*(?:小屋|家|村)|build/i.test(clause);
    const gather = /集め|集める|集めて|採集|採掘|補充|確保|増や|gather|collect/i.test(clause);
    if ([auto, rest, build, gather].filter(Boolean).length !== 1) throw new Error(`指示を1文ずつ区切ってください。${help}`);
    if ((auto || rest) && /[0-9]|[一二三四五六七八九十]+(?:時間|分|日)/.test(clause)) throw new Error('休息はゲーム内1時間です。人数・時間の指定にはまだ対応していません。');
    if (auto) return { action: 'auto', target };
    if (rest) return { action: 'rest', target };
    if (build) {
      if (named.length) throw new Error('建築は村の仕事として指示してください。建築家が担当します。');
      const locations = [clause.includes('川'), clause.includes('森')];
      if (locations.every(Boolean)) throw new Error('建築場所は「村の近く」「川の近く」「森の近く」のいずれかにしてください。');
      const match = clause.match(/([0-9]+|[一二三四五六七八九十]+)\s*(?:軒|棟)/);
      const numbers: Record<string, number> = { 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10 };
      if (/[0-9一二三四五六七八九十]/.test(clause) && !match) throw new Error('建築数は「1軒」のように指定してください。');
      const count = match ? (numbers[match[1]] ?? Number(match[1])) : clause.includes('村') ? 3 : 1;
      if (!Number.isInteger(count) || count < 1 || count > 5) throw new Error('一度に建てられる小屋は1〜5軒です。');
      return { action: 'build', building: 'hut', count, location: locations[0] ? 'river' : locations[1] ? 'forest' : 'village' };
    }
    const resources = [{ resource: 'wood' as const, match: /木材|木|wood/i }, { resource: 'stone' as const, match: /石材|石|stone/i }, { resource: 'food' as const, match: /食料|食べ物|果実|food/i }].filter(r => r.match.test(clause));
    if (/[0-9一二三四五六七八九十百千万億]|\b\w+\s+(?:minutes|hours)\b/i.test(clause)) throw new Error('採集の優先はゲーム内4時間です。数量・時間の指定にはまだ対応していません。');
    if (resources.length !== 1) throw new Error('採集する資源を1文に1種類ずつ指定してください。食料・木材・石材に対応しています。');
    return { action: 'gather', target, resource: resources[0].resource };
  });
  if (!commands.length) throw new Error(help);
  return interpretationSchema.parse({ commands, message: '' }).commands;
}
