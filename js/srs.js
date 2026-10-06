/* ---------- Spaced repetition (simplified SM-2, tuned for a 2-month sprint) ----------
   Intervals in days by "box" (consecutive successes): 0→1 (ngày mai), 1→3, 2→7, 3→14, 4→30, 5→60.
   Wrong answer: back to box 0, due tomorrow, lapses+1.
   "Easy" (dễ) jumps one extra box. "Hard" (khó) stays in the same box, due in 2 days.
*/
import { DAY, startOfDay } from './util.js';

export const INTERVALS = [1, 3, 7, 14, 30, 60];

export function newCard(now = Date.now(), reason = 'flag') {
  return { box: 0, due: startOfDay(now), reps: 0, lapses: 0, added: now, last: null, reason, flagged: reason === 'flag' };
}

/**
 * @param card existing card
 * @param grade 'again' | 'hard' | 'good' | 'easy'
 */
export function review(card, grade, now = Date.now()) {
  const c = { ...card, reps: card.reps + 1, last: now };
  if (grade === 'again') {
    c.box = 0; c.lapses = (c.lapses || 0) + 1;
    c.due = startOfDay(now) + DAY;
  } else if (grade === 'hard') {
    c.due = startOfDay(now) + 2 * DAY;
  } else {
    const step = grade === 'easy' ? 2 : 1;
    c.box = Math.min(INTERVALS.length - 1, c.box + step);
    c.due = startOfDay(now) + INTERVALS[c.box] * DAY;
  }
  return c;
}

export const isDue = (card, now = Date.now()) => card.due <= now;

export function boxLabel(box) {
  return ['Mới', '3 ngày', '1 tuần', '2 tuần', '1 tháng', 'Thuộc'][Math.min(box, 5)];
}
