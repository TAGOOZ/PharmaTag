/** Business-day date (YYYY-MM-DD) in the shop timezone.
 *
 * The server derives its business day in Africa/Cairo (`business_date()`); a
 * UTC default (`new Date().toISOString().slice(0, 10)`) posts the wrong day
 * near midnight (Cairo is UTC+2/+3). Clients that must send an explicit
 * `datee` (journals, vouchers — the server requires it) default through here.
 */
export function businessToday(now: Date = new Date(), timeZone = 'Africa/Cairo'): string {
  if (Number.isNaN(now.getTime())) throw new RangeError('invalid date');
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}
