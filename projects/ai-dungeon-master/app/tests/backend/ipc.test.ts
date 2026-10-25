import { describe, expect, it } from 'vitest';
import { AIDM_ERROR_CODES, aidmError, isAidmError } from '../../shared/errors.js';
import { createHandlers } from '../../electron/main/ipc.js';
import { CampaignService } from '../../electron/main/service.js';
import { makeFixture } from './helpers.js';

describe('IPC boundary validation', () => {
  it('rejects oversized and malformed args before they reach the service', async () => {
    const fx = makeFixture();
    const handlers = createHandlers(new CampaignService(fx.db));
    const create = handlers['aidm:campaigns-create'];
    if (!create) throw new Error('handler missing');
    await expect(create({ name: '' })).rejects.toMatchObject({
      code: AIDM_ERROR_CODES.INPUT_INVALID,
    });
    await expect(create({ name: 'x'.repeat(201) })).rejects.toMatchObject({
      code: AIDM_ERROR_CODES.INPUT_INVALID,
    });
    await expect(create({ name: 'Ok', hacker: true })).rejects.toMatchObject({
      code: AIDM_ERROR_CODES.INPUT_INVALID,
    });
    const ok = (await create({ name: 'Via IPC' })) as { name: string };
    expect(ok.name).toBe('Via IPC');
  });

  it('maps service named errors through unchanged', async () => {
    const fx = makeFixture();
    const handlers = createHandlers(new CampaignService(fx.db));
    const roll = handlers['aidm:dice-roll'];
    if (!roll) throw new Error('handler missing');
    await expect(roll('missing-campaign', { notation: '2d6' })).rejects.toMatchObject({
      code: 'CAMPAIGN_NOT_FOUND',
    });
    const campaign = await fx.service.campaignsCreate({ name: 'X', seed: 'x' });
    await expect(roll(campaign.id, { notation: 'bogus' })).rejects.toMatchObject({
      code: 'DICE_NOTATION_INVALID',
    });
  });

  it('error objects survive the plain-error conversion', () => {
    const err = aidmError(AIDM_ERROR_CODES.IMPORT_INVALID, 'bad');
    expect(isAidmError(err)).toBe(true);
    expect(isAidmError({ code: 'NOPE', message: 'x' })).toBe(false);
    expect(isAidmError(new Error('plain'))).toBe(false);
  });
});
