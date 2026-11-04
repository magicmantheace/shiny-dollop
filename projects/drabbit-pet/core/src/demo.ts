// Headless lifecycle demo: fast-forwards a drabbit from egg to adult
// under a simple caretaker policy and prints a readable diary.
// Fully deterministic — the start time is fixed, the sim has no clock.

import {
  advance,
  clean,
  createSave,
  feed,
  giveMedicine,
  hatch,
  play,
  putToSleep,
  serialize,
  wake,
  type PetEvent,
  type PetState,
} from "./index.js";

const MIN = 60_000;
const T0 = Date.UTC(2026, 0, 1, 8, 0, 0); // fixed epoch: 2026-01-01 08:00 UTC

function stamp(t: number): string {
  const d = new Date(t);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `Day ${d.getUTCDate()} ${hh}:${mm}`;
}

function diary(events: PetEvent[]): void {
  for (const e of events) {
    console.log(`  [${stamp(e.t)}] ${e.kind}: ${e.detail}`);
  }
}

function statusLine(p: PetState): string {
  const n = p.needs;
  const f = (v: number) => Math.round(v);
  return (
    `stage=${p.stage}${p.adultForm ? `/${p.adultForm}` : ""} mood=${p.mood} ` +
    `hunger=${f(n.hunger)} happiness=${f(n.happiness)} energy=${f(n.energy)} ` +
    `clean=${f(n.cleanliness)} health=${f(p.health)} care=${f(p.careScore)} messes=${p.messes}`
  );
}

let env = createSave({ id: "demo-pip", name: "Pip", fur: "royal" }, T0);
let pet = env.pet;
console.log(`Pip the drabbit — a headless life, fast-forwarded.`);
console.log(`  [${stamp(T0)}] An egg arrives (royal purple fur, allegedly).`);

pet = advance(pet, T0 + 10 * MIN).state;
diary(pet.events.slice(-1));
pet = hatch(pet, T0 + 10 * MIN).state;
console.log(`  [${stamp(T0 + 10 * MIN)}] hatched: Pip is out! ${statusLine(pet)}`);

const STEP = 15 * MIN;
let now = T0 + 10 * MIN;
let lastStatus = "";
while (pet.stage !== "adult" && pet.stage !== "dead") {
  now += STEP;
  let r = advance(pet, now);
  pet = r.state;
  diary(r.events);

  // A simple, attentive caretaker.
  if (pet.stage !== "dead" && pet.stage !== "egg") {
    if (pet.sick) {
      r = giveMedicine(pet, now);
      pet = r.state;
      diary(r.events.slice(0));
    } else if (pet.asleep && pet.needs.energy > 92) {
      pet = wake(pet, now).state;
    } else if (!pet.asleep && pet.needs.energy < 18) {
      pet = putToSleep(pet, now).state;
    } else if (!pet.asleep && pet.messes > 0) {
      pet = clean(pet, now).state;
    } else if (!pet.asleep && pet.needs.hunger < 45) {
      pet = feed(pet, now, "meal").state;
    } else if (!pet.asleep && pet.needs.happiness < 45) {
      pet = play(pet, now).state;
    } else if (!pet.asleep && pet.needs.cleanliness < 40) {
      pet = clean(pet, now).state;
    }
  }

  const line = statusLine(pet);
  if (line !== lastStatus && pet.ageMs % (3 * 60 * MIN) < STEP) {
    console.log(`  [${stamp(now)}] ${line}`);
    lastStatus = line;
  }
}

// A few more hours of adult life.
for (let i = 0; i < 8 && pet.stage === "adult"; i++) {
  now += 30 * MIN;
  const r = advance(pet, now);
  pet = r.state;
  diary(r.events);
  if (pet.sick) pet = giveMedicine(pet, now).state;
  else if (pet.asleep && pet.needs.energy > 92) pet = wake(pet, now).state;
  else if (!pet.asleep && pet.needs.energy < 18) pet = putToSleep(pet, now).state;
  else if (!pet.asleep && pet.needs.hunger < 45) pet = feed(pet, now, "meal").state;
  else if (!pet.asleep && pet.needs.happiness < 45) pet = play(pet, now).state;
  if (pet.messes > 0) pet = clean(pet, now).state;
}

env = { ...env, pet };
console.log(`\nFinal: ${statusLine(pet)}`);
console.log(`Events recorded: ${pet.events.length}`);
console.log(`Save size: ${serialize(env).length} bytes (schema v${env.schemaVersion}, generation ${env.lineage.generation})`);
if (pet.stage !== "adult") {
  console.error(`Demo FAILED: expected Pip to reach adulthood, got stage=${pet.stage}`);
  process.exit(1);
}
console.log(`Pip reached adulthood as a ${pet.adultForm} drabbit. The brain works.`);
