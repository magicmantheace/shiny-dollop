import { createSave, hatch, type PetState } from "../src/index.js";

export const MIN = 60_000;
export const H = 60 * MIN;
export const T0 = 1_700_000_000_000; // arbitrary fixed epoch; the sim has no clock

export function egg(id: string, t: number = T0): PetState {
  return createSave({ id, name: id, fur: "royal" }, t).pet;
}

export function hatched(id: string, t: number = T0): PetState {
  return hatch(egg(id, t), t + 10 * MIN).state;
}
