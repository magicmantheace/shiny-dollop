import type { AutoCareState } from '../shared/api-types.js';
import { autoCareActionsFor } from '../shared/auto-care.js';
import { dispatchAction } from './action-dispatch.js';
import type { AutoCareConfigStore } from './auto-care-config.js';
import type { PetService } from './pet-service.js';

/**
 * Auto-care service (owner-requested, 2026-11-05): while the
 * persisted toggle is on, the app performs due care actions itself
 * through the shared action dispatcher — the same front door the
 * panel and the phone use, so an auto-care action is an ordinary,
 * event-logged action. Evaluation rides the pet's existing change
 * notifications (the tick cadence); there is no second clock and
 * nothing here touches the sim.
 */
export class AutoCareService {
  private config = { enabled: false };
  private acting = false;

  constructor(
    private readonly deps: {
      store: AutoCareConfigStore;
      service: PetService;
      now?: () => number;
      log?: (msg: string) => void;
    },
  ) {}

  init(): void {
    const { config, outcome } = this.deps.store.load(
      (this.deps.now ?? Date.now)(),
    );
    this.config = config;
    this.deps.log?.(
      `[drabbit] auto-care ${config.enabled ? 'ON' : 'off'} (config ${outcome})`,
    );
    if (config.enabled) this.consider();
  }

  getState(): AutoCareState {
    return { enabled: this.config.enabled };
  }

  setEnabled(enabled: boolean): AutoCareState {
    this.config = { enabled };
    this.deps.store.save(this.config);
    this.deps.log?.(`[drabbit] auto-care switched ${enabled ? 'ON' : 'off'}`);
    if (enabled) this.consider();
    return this.getState();
  }

  /**
   * Evaluate the current summary and perform whatever is due.
   * Called from the pet's change notifications. The acting guard
   * keeps the notifications raised by our own actions from
   * re-entering; after a batch we re-read the summary and repeat
   * (bounded) in case an earlier action unblocked a later one.
   */
  consider(): void {
    if (!this.config.enabled || this.acting) return;
    this.acting = true;
    try {
      for (let round = 0; round < 3; round += 1) {
        const actions = autoCareActionsFor(this.deps.service.getSummary());
        if (actions.length === 0) break;
        for (const kind of actions) {
          const result = dispatchAction(this.deps.service, kind);
          if (!result.ok) {
            this.deps.log?.(
              `[drabbit] auto-care ${kind} declined: ${result.error.code}`,
            );
          }
        }
      }
    } finally {
      this.acting = false;
    }
  }
}
