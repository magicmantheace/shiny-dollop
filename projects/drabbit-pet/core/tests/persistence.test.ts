import { describe, expect, it } from "vitest";
import {
  advance,
  createSave,
  feed,
  parse,
  serialize,
} from "../src/index.js";
import { hatched, H, MIN } from "./helpers.js";

describe("persistence", () => {
  it("round-trips a lived-in save byte-identically", () => {
    let pet = hatched("save-1");
    pet = advance(pet, pet.lastTickAt + 3 * H).state;
    pet = feed(pet, pet.lastTickAt, "meal").state;
    const env = {
      schemaVersion: 1,
      pet,
      lineage: {
        generation: 2,
        ancestors: [
          {
            name: "Old Pip",
            fur: "ember" as const,
            adultForm: "content" as const,
            bornAt: 0,
            diedAt: 1000,
            deathCause: "neglect",
          },
        ],
      },
    };
    const text = serialize(env);
    const parsed = parse(text);
    expect(serialize(parsed)).toBe(text);
    expect(parsed.pet).toEqual(pet);
    expect(parsed.lineage.ancestors).toHaveLength(1);
    expect(parsed.schemaVersion).toBe(1);
    expect(parsed.pet.schemaVersion).toBe(1);
  });

  it("serializes deterministically: identical inputs give identical bytes", () => {
    const a = createSave({ id: "same", name: "Same", fur: "sky" }, 42_000);
    const b = createSave({ id: "same", name: "Same", fur: "sky" }, 42_000);
    expect(serialize(a)).toBe(serialize(b));
    const advanced = advance(a.pet, 42_000 + 5 * MIN).state;
    expect(serialize({ ...a, pet: advanced })).toBe(serialize({ ...b, pet: advanced }));
  });

  it("rejects non-JSON and malformed saves", () => {
    expect(() => parse("not json at all")).toThrowError(
      expect.objectContaining({ code: "bad_save" }),
    );
    expect(() => parse("{}")).toThrowError(expect.objectContaining({ code: "bad_save" }));
    expect(() => parse('{"schemaVersion":1}')).toThrowError(
      expect.objectContaining({ code: "bad_save" }),
    );
  });

  it("rejects saves from a newer schema version", () => {
    const env = createSave({ id: "future", name: "Future", fur: "sky" }, 0);
    const future = serialize({ ...env, schemaVersion: 99 });
    expect(() => parse(future)).toThrowError(expect.objectContaining({ code: "bad_save" }));
  });
});
