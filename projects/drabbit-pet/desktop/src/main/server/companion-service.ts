import type { CompanionState } from '../../shared/api-types.js';
import { dispatchAction } from '../action-dispatch.js';
import type { Clock, PetService } from '../pet-service.js';
import {
  generateCompanionToken,
  type CompanionConfig,
  type CompanionConfigStore,
  DEFAULT_COMPANION_CONFIG,
} from './companion-config.js';
import { CompanionServer } from './companion-server.js';

/**
 * Coordinates the companion config store + HTTP server: the server
 * runs iff the persisted config says `enabled`, and config changes
 * (enable toggle, token regeneration, host/port edits) take effect
 * by stopping and restarting the server. A bind failure (port in
 * use) lands in a panel-visible `error` state — never a crash.
 *
 * Electron-free: PetService, the config store, and the clock are
 * injected, so tests drive the whole lifecycle in plain Node.
 */

export interface CompanionServiceDeps {
  store: CompanionConfigStore;
  service: PetService;
  clock: Clock;
  log?: (msg: string) => void;
}

export class CompanionService {
  private config: CompanionConfig = { ...DEFAULT_COMPANION_CONFIG };
  private server: CompanionServer | null = null;
  private status: CompanionState['status'] = 'off';
  private errorMessage: string | null = null;
  /** Serializes lifecycle operations so toggles can't interleave. */
  private chain: Promise<unknown> = Promise.resolve();

  constructor(private readonly deps: CompanionServiceDeps) {}

  /** Load the persisted config and start the server if it was left on. */
  init(): Promise<CompanionState> {
    return this.enqueue(async () => {
      const { config, outcome } = this.deps.store.load(this.deps.clock.now());
      this.config = config;
      if (outcome === 'fresh-corrupt') {
        this.deps.log?.('[drabbit] companion config recovered from corruption; using defaults');
      }
      if (this.config.enabled) {
        if (!this.config.token) {
          this.config = { ...this.config, token: generateCompanionToken() };
          this.deps.store.save(this.config);
        }
        await this.startServer();
      }
      return this.getState();
    });
  }

  getState(): CompanionState {
    return {
      enabled: this.config.enabled,
      status: this.status,
      host: this.config.host,
      port: this.config.port,
      url: this.status === 'on' ? `http://${this.config.host}:${this.config.port}` : null,
      error: this.status === 'error' ? this.errorMessage : null,
      token: this.config.token,
      stats: this.server?.getStats() ?? null,
    };
  }

  /** The master switch from the care panel. */
  setEnabled(enabled: boolean): Promise<CompanionState> {
    return this.enqueue(async () => {
      this.config = { ...this.config, enabled };
      if (enabled && !this.config.token) {
        // The token is born with the first enable, never before.
        this.config = { ...this.config, token: generateCompanionToken() };
      }
      this.deps.store.save(this.config);
      if (enabled) {
        if (this.status !== 'on') await this.startServer();
      } else {
        await this.stopServer();
        this.status = 'off';
        this.errorMessage = null;
      }
      return this.getState();
    });
  }

  /**
   * Mint a new token and persist it. If the server is running it is
   * restarted, so the old token stops working immediately.
   */
  regenerateToken(): Promise<CompanionState> {
    return this.enqueue(async () => {
      this.config = { ...this.config, token: generateCompanionToken() };
      this.deps.store.save(this.config);
      if (this.status === 'on') {
        await this.stopServer();
        await this.startServer();
      } else if (this.config.enabled && this.status === 'error') {
        await this.startServer(); // retry with the fresh token
      }
      return this.getState();
    });
  }

  /** Stop the server (app quit). The persisted switch is untouched. */
  shutdown(): Promise<void> {
    return this.enqueue(async () => {
      await this.stopServer();
    }).then(() => undefined);
  }

  // -- internals ------------------------------------------------------------

  private enqueue<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.chain.then(fn, fn);
    this.chain = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  }

  private async startServer(): Promise<void> {
    const { service, clock } = this.deps;
    const server = new CompanionServer({
      getConfig: () => this.config,
      tick: () => service.tick(),
      getSummary: () => service.getSummary(),
      getEventsSince: (since) => service.getEventsSince(since),
      getEventCursor: () => service.getEventCursor(),
      dispatch: (kind) => dispatchAction(service, kind),
      clock,
    });
    try {
      await server.start();
      this.server = server;
      this.status = 'on';
      this.errorMessage = null;
      this.deps.log?.(
        `[drabbit] companion server listening on http://${this.config.host}:${this.config.port}`,
      );
    } catch (err) {
      this.server = null;
      this.status = 'error';
      this.errorMessage = err instanceof Error ? err.message : String(err);
      this.deps.log?.(`[drabbit] companion server failed to start: ${this.errorMessage}`);
    }
  }

  private async stopServer(): Promise<void> {
    const server = this.server;
    this.server = null;
    if (server) await server.stop();
    if (this.status === 'on') this.status = 'off';
  }
}
