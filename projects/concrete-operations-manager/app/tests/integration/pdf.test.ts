import { afterEach, describe, expect, it } from 'vitest';
import zlib from 'node:zlib';
import { makeTestDb, addTestCustomer, addTestJob, addTestPour } from '../helpers';
import type { DatabaseSync } from 'node:sqlite';
import { renderInvoicePdf } from '../../electron/main/export/pdf';
import { createQuote, issueQuote } from '../../electron/main/db/quotes';
import { createInvoice } from '../../electron/main/db/invoices';
import { setDeliveredLiters } from '../../electron/main/db/pours';

interface TextBlock {
  x: number;
  y: number;
  text: string;
}

/** Inflate the PDF content streams and extract text blocks with positions. */
function extractTextBlocks(buffer: Buffer): TextBlock[] {
  const raw = buffer.toString('latin1');
  let decoded = '';
  const streamRe = /stream\r?\n/g;
  let m: RegExpExecArray | null;
  while ((m = streamRe.exec(raw)) !== null) {
    const start = m.index + m[0].length;
    const end = raw.indexOf('endstream', start);
    if (end < 0) continue;
    try {
      decoded += zlib.inflateSync(Buffer.from(raw.slice(start, end), 'latin1')).toString('latin1');
    } catch {
      // Not a flate stream — skip.
    }
  }
  const blocks: TextBlock[] = [];
  const blockRe = /1 0 0 1 ([\d.-]+) ([\d.-]+) Tm[\s\S]*?\[([^\]]*)\] TJ/g;
  let b: RegExpExecArray | null;
  while ((b = blockRe.exec(decoded)) !== null) {
    const hexParts = [...b[3]!.matchAll(/<([0-9a-fA-F]+)>/g)].map((h) =>
      Buffer.from(h[1]!, 'hex').toString('latin1'),
    );
    blocks.push({ x: Number(b[1]), y: Number(b[2]), text: hexParts.join('') });
  }
  return blocks;
}

let db: DatabaseSync;
afterEach(() => {
  try {
    db?.close();
  } catch {
    // ignore
  }
});

describe('invoice PDF export', () => {
  it('renders a non-empty PDF for an issued invoice', async () => {
    db = makeTestDb();
    const customer = addTestCustomer(db, 'PDF Test Customer');
    const job = addTestJob(db, customer.id);
    const pour = addTestPour(db, job.id, 2500);
    const quote = issueQuote(db, createQuote(db, job.id, null).id);
    setDeliveredLiters(db, pour.id, 2480);
    const invoice = createInvoice(db, quote.id);

    const { buffer, fileName } = await renderInvoicePdf(db, invoice.id);
    expect(fileName).toBe(`${invoice.invoiceNumber}.pdf`);
    expect(buffer.length).toBeGreaterThan(1000);
    // PDF magic bytes.
    expect(buffer.subarray(0, 5).toString('ascii')).toBe('%PDF-');
  });

  it('starts the next charge below the full height of a multi-line charge row', async () => {
    db = makeTestDb();
    const customer = addTestCustomer(db, 'PDF Test Customer');
    const job = addTestJob(db, customer.id);
    const pour = addTestPour(db, job.id, 2500);
    const quote = issueQuote(db, createQuote(db, job.id, null).id);
    setDeliveredLiters(db, pour.id, 2480);
    const invoice = createInvoice(db, quote.id);

    // Craft a first charge whose description occupies three rendered lines
    // (label + a detail long enough to wrap at 9pt in the 400pt column),
    // followed by a second charge that must not overlap it.
    const lines = [
      {
        kind: 'concrete',
        label: 'FIRSTCHARGE label',
        detail:
          'FIRSTDETAIL long detail text that should wrap onto more than one rendered line at nine point inside a four hundred point column width for sure yes indeed wrapping',
        amountCents: 11111,
      },
      { kind: 'fee', label: 'SECONDCHARGE label', amountCents: 22222 },
    ];
    db.prepare('UPDATE invoices SET lines_json = ? WHERE id = ?').run(
      JSON.stringify(lines),
      invoice.id,
    );

    const { buffer } = await renderInvoicePdf(db, invoice.id);
    const blocks = extractTextBlocks(buffer);

    const secondIdx = blocks.findIndex((b) => b.text.includes('SECONDCHARGE'));
    expect(secondIdx).toBeGreaterThan(0);
    // Description-column blocks (x near the left margin) from the first
    // charge's label up to — but not including — the second charge.
    const firstIdx = blocks.findIndex((b) => b.text.includes('FIRSTCHARGE'));
    expect(firstIdx).toBeGreaterThanOrEqual(0);
    const descriptionBlocks = blocks.slice(firstIdx, secondIdx).filter((b) => b.x < 100);
    // Label + at least two wrapped detail lines.
    expect(descriptionBlocks.length).toBeGreaterThanOrEqual(3);
    // PDF text matrices: y decreases down the page. The lowest description
    // line has the smallest y; the next charge must start clearly below it
    // (previously the amount's single-line height reset the advance, so the
    // second charge was drawn inside the first charge's detail text).
    const descriptionBottomY = Math.min(...descriptionBlocks.map((b) => b.y));
    const secondChargeY = blocks[secondIdx]!.y;
    expect(secondChargeY).toBeLessThan(descriptionBottomY - 10);
  });

  it('fails clearly for a missing invoice', async () => {
    db = makeTestDb();
    await expect(renderInvoicePdf(db, 9999)).rejects.toThrow(/does not exist/);
  });
});
