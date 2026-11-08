/**
 * Invoice renderer. Pure and deterministic: identical (data, tokens, format)
 * inputs produce byte-identical HTML. No timestamps. All user values escaped.
 */
import type { ExportFormat, ThemeTokens } from '../../../shared/types';
import { escapeHtml } from '../util/escape';

interface LineItem {
  desc: string;
  qty: number;
  price: number;
}

function toLineItems(value: unknown): LineItem[] {
  if (!Array.isArray(value)) return [];
  return value.map((raw) => {
    const item = (raw ?? {}) as Record<string, unknown>;
    return {
      desc: typeof item.desc === 'string' ? item.desc : '',
      qty: Number(item.qty) || 0,
      price: Number(item.price) || 0,
    };
  });
}

function money(value: number): string {
  return value.toFixed(2);
}

export function renderInvoice(
  data: Record<string, unknown>,
  tokens: ThemeTokens,
  format: ExportFormat,
): string {
  const t = tokens;
  const s = t.spacing;
  const items = toLineItems(data.lineItems);
  const subtotal = items.reduce((sum, it) => sum + it.qty * it.price, 0);
  const taxRate = Number(data.taxRate) || 0;
  const tax = (subtotal * taxRate) / 100;
  const total = subtotal + tax;

  const rows = items
    .map(
      (it) => `          <tr>
            <td>${escapeHtml(it.desc)}</td>
            <td class="num">${escapeHtml(money(it.qty))}</td>
            <td class="num">${escapeHtml(money(it.price))}</td>
            <td class="num">${escapeHtml(money(it.qty * it.price))}</td>
          </tr>`,
    )
    .join('\n');

  const notes = typeof data.notes === 'string' && data.notes.length > 0
    ? `      <section class="notes">
        <h2>Notes</h2>
        <p>${escapeHtml(data.notes)}</p>
      </section>\n`
    : '';

  return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Invoice ${escapeHtml(data.invoiceNumber)}</title>
    <style>
      :root { color-scheme: light; }
      * { box-sizing: border-box; }
      body { margin: 0; background: ${t.bg}; color: ${t.text}; font-family: ${t.bodyFont}; }
      main.invoice { max-width: 760px; margin: 0 auto; padding: ${s * 2}px; }
      header.inv-head { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid ${t.accent}; padding-bottom: ${s}px; margin-bottom: ${s * 1.5}px; }
      h1 { font-family: ${t.headingFont}; margin: 0 0 ${s / 2}px 0; color: ${t.accent}; }
      .meta { text-align: right; font-size: 0.9em; }
      .parties { display: flex; justify-content: space-between; gap: ${s}px; margin-bottom: ${s * 1.5}px; }
      .parties h2 { font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.08em; color: ${t.accent}; margin: 0 0 ${s / 4}px 0; font-family: ${t.headingFont}; }
      table.items { width: 100%; border-collapse: collapse; margin-bottom: ${s}px; }
      table.items th, table.items td { padding: ${s / 2}px; border-bottom: 1px solid ${t.text}; text-align: left; }
      table.items th { font-family: ${t.headingFont}; color: ${t.accent}; }
      table.items td.num, table.items th.num { text-align: right; }
      .totals { margin-left: auto; width: 240px; }
      .totals .row { display: flex; justify-content: space-between; padding: ${s / 4}px 0; }
      .totals .grand { font-weight: bold; font-size: 1.15em; border-top: 2px solid ${t.accent}; margin-top: ${s / 2}px; padding-top: ${s / 2}px; }
      .notes h2 { font-family: ${t.headingFont}; color: ${t.accent}; font-size: 1em; }
      footer.inv-foot { margin-top: ${s * 2}px; font-size: 0.8em; opacity: 0.8; }
      body.format-print main.invoice { max-width: none; }
      @media print {
        main.invoice { padding: 0; }
        @page { size: letter; margin: 18mm; }
      }
    </style>
  </head>
  <body class="format-${format}">
    <main class="invoice">
      <header class="inv-head">
        <div>
          <h1>${escapeHtml(data.businessName)}</h1>
          <div>Invoice ${escapeHtml(data.invoiceNumber)}</div>
        </div>
        <div class="meta">
          <div>Issued: ${escapeHtml(data.issueDate)}</div>
        </div>
      </header>
      <div class="parties">
        <div>
          <h2>From</h2>
          <div>${escapeHtml(data.businessName)}</div>
        </div>
        <div>
          <h2>Bill to</h2>
          <div>${escapeHtml(data.clientName)}</div>
        </div>
      </div>
      <table class="items">
        <thead>
          <tr><th>Description</th><th class="num">Qty</th><th class="num">Unit price</th><th class="num">Amount</th></tr>
        </thead>
        <tbody>
${rows}
        </tbody>
      </table>
      <div class="totals">
        <div class="row"><span>Subtotal</span><span>${escapeHtml(money(subtotal))}</span></div>
        <div class="row"><span>Tax (${escapeHtml(money(taxRate))}%)</span><span>${escapeHtml(money(tax))}</span></div>
        <div class="row grand"><span>Total</span><span>${escapeHtml(money(total))}</span></div>
      </div>
${notes}      <footer class="inv-foot">Generated with Digital Product Template Factory</footer>
    </main>
  </body>
</html>
`;
}
