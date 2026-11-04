import { describe, expect, it } from 'vitest';
import { AIDM_ERROR_CODES, aidmError, isAidmError } from '../../shared/errors.js';
import { createHandlers } from '../../electron/main/ipc.js';
import { CampaignService } from '../../electron/main/service.js';
import { makeFixture } from './helpers.js';

describe('IPC boundary validation', () => {
  it('returns structured failures for oversized and malformed args before they reach the service', async () => {
    const fx = makeFixture();
    const handlers = createHandlers(new CampaignService(fx.db));
    const create = handlers['aidm:campaigns-create'];
    if (!create) throw new Error('handler missing');
    await expect(create({ name: '' })).resolves.toMatchObject({
      ok: false,
      error: { code: AIDM_ERROR_CODES.INPUT_INVALID, message: expect.any(String) },
    });
    await expect(create({ name: 'x'.repeat(201) })).resolves.toMatchObject({
      ok: false,
      error: { code: AIDM_ERROR_CODES.INPUT_INVALID, message: expect.any(String) },
    });
    await expect(create({ name: 'Ok', hacker: true })).resolves.toMatchObject({
      ok: false,
      error: { code: AIDM_ERROR_CODES.INPUT_INVALID, message: expect.any(String) },
    });
    await expect(create({ name: 'Via IPC' })).resolves.toMatchObject({
      ok: true,
      value: { name: 'Via IPC' },
    });
  });

  it('returns service named errors unchanged in the structured failure envelope', async () => {
    const fx = makeFixture();
    const handlers = createHandlers(new CampaignService(fx.db));
    const roll = handlers['aidm:dice-roll'];
    if (!roll) throw new Error('handler missing');
    await expect(roll('missing-campaign', { notation: '2d6' })).resolves.toMatchObject({
      ok: false,
      error: { code: 'CAMPAIGN_NOT_FOUND', message: expect.any(String) },
    });
    const campaign = await fx.service.campaignsCreate({ name: 'X', seed: 'x' });
    await expect(roll(campaign.id, { notation: 'bogus' })).resolves.toMatchObject({
      ok: false,
      error: { code: 'DICE_NOTATION_INVALID', message: expect.any(String) },
    });
  });

  it('error objects survive the plain-error conversion', () => {
    const err = aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, 'bad');
    expect(isAidmError(err)).toBe(true);
    expect(isAidmError({ code: 'NOPE', message: 'x' })).toBe(false);
    expect(isAidmError(new Error('plain'))).toBe(false);
  });
});
