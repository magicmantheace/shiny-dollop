import type { ApiError } from '../shared/types.js';

export interface IpcOk<T> {
  ok: true;
  data: T;
}
export interface IpcFail {
  ok: false;
  error: ApiError;
}
export type IpcResult<T> = IpcOk<T> | IpcFail;

declare global {
  interface Window {
    vcc: {
      profiles: {
        list(): Promise<IpcResult<import('../shared/types.js').ProfileSummary[]>>;
        get(id: number): Promise<IpcResult<import('../shared/types.js').CalibrationProfile & { id: number }>>;
        create(profile: unknown): Promise<IpcResult<{ id: number }>>;
        update(id: number, profile: unknown): Promise<IpcResult<{ id: number }>>;
        remove(id: number): Promise<IpcResult<{ id: number }>>;
      };
      calc: {
        run(input: unknown): Promise<
          IpcResult<{ id: number; result: import('../shared/types.js').CalculationResult; massUnit: string }>
        >;
      };
      history: {
        list(): Promise<IpcResult<import('../shared/types.js').CalculationRecord[]>>;
      };
      export_: {
        envelope(profileId: number): Promise<IpcResult<{ filePath?: string; canceled?: boolean }>>;
        csv(calculationId: number): Promise<IpcResult<{ filePath?: string; canceled?: boolean }>>;
      };
      import_: {
        envelope(): Promise<IpcResult<{ id?: number; profileName?: string; canceled?: boolean }>>;
      };
    };
  }
}

export async function unwrap<T>(p: Promise<IpcResult<T>>): Promise<T> {
  const r = await p;
  if (!r.ok) throw new Error(r.error.message);
  return r.data;
}
