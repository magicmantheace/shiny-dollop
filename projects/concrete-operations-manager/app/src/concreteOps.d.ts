/// <reference types="vite/client" />
import type { ConcreteOpsApi } from '../shared/api-types';

declare global {
  interface Window {
    concreteOps: ConcreteOpsApi;
  }
}

export {};
