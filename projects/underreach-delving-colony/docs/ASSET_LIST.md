# Underreach — complete asset list

Everything the game needs from the art pipeline (Game Asset
Builder), written 2026-11-10 after S1–S5 shipped. Statuses:

- ✅ **Have** — catalogued in the Game Asset Builder, usable now.
- 🔄 **Stand-in** — the frontend uses a catalogued substitute today.
- 🛑 **Stopped queue** — was in the 2026-11-10 pipeline run that the
  owner stopped; resumable when the PC lane reopens.
- ⬜ **Not started** — designed, not yet in any queue.

Rigged characters need the pipeline's animation pass (idle / walk /
run + role clips). Props go through the unrigged `--prop` route.
Terrain itself is code-generated voxels; what the pipeline owes the
terrain is dressing and kit pieces per band.

## 1. Delvers & the player

| Asset | Spec | Status |
|---|---|---|
| Delver (base colonist) | Rigged biped; idle/walk/run + mine swing, carry walk, tend, eat, sleep (lying), downed (lying), rescue-carry | ✅ catalogued 2026-11-11 (arm-separation-gated A-pose rebuild; clips idle/walk/run/bounce) and in frontend use — snow-goblin stand-in retired |
| The Frontier Bearer (player) | Rigged biped with the great lantern; idle/walk/run + plant-light, carve swing | ⬜ (co-op: up to 4 tint variants) |
| Miner kit — pickaxe + helmet lamp | Hand/back props, attachable | ⬜ |
| Hauler kit — carry sack / ore basket | Back prop | ⬜ |
| Farmer kit — sickle + pouch | Hand/belt props | ⬜ |
| Herbalist kit — herb bundle + satchel | Hand/shoulder props | ⬜ |
| Spore mask | Worn face prop (equipped visual for the S5 gate) | ⬜ |
| Harness + rope | Worn prop (Crystal Dark gate) | ⬜ |
| Quiet gear — padded wraps | Worn prop set (Crystal Dark gate) | ⬜ |
| Cooling gear — insulated suit pieces | Worn prop set (Magma gate) | ⬜ |

## 2. Creatures

| Asset | Spec | Status |
|---|---|---|
| Gloam rat | Rigged quadruped, small; idle/walk/run + bite lunge | ⬜ (sim kind exists) |
| Deep lurker | Rigged quadruped, large; idle/walk/run + lunge | ✅ catalogued 2026-11-12 as gloam-lurker (clips idle/walk/run/shiver; leg-separation gates passed) and in frontend use — ember-dragon stand-in retired |
| Shallows starter creature | Small cave beast, quadruped | ⬜ design TBD |
| Fungal ambusher | Spore-hulk quadruped; burst-from-ground signature | ⬜ design TBD |
| Drowned swimmer | Eel-like swimmer rig | ⬜ design TBD |
| Crystal sound-hunter | Blind quadruped, huge ears; head-cock signature | ⬜ design TBD |
| Magma creature | Basalt-plated quadruped | ⬜ design TBD |

## 3. Lanterns & light infrastructure

One prop per tier (the design's progression: radius / burn /
steadiness / tags all read off these):

| Asset | Tier / role | Status |
|---|---|---|
| Torch on a stand | Tier 0 — torches/charcoal | ⬜ |
| Oil lantern on a post | Tier 1 — the colony standard | ✅ catalogued and in frontend use 2026-11-11 (OmniLight + emissive flame marker kept) |
| Fungal-oil lantern | Tier 2 — spore-repellent glow | ⬜ |
| Sealed pressure lantern | Tier 3 — waterproof (Drowned) | ⬜ |
| Crystal-heart lantern | Tier 4 — focused beam (Crystal Dark) | ⬜ |
| Thermal lamp | Tier 5 — vent-fed (Magma) | ⬜ |
| Piped light-spine segment | Infrastructure — lit main routes | ⬜ |
| Crystal relay | Infrastructure — light relay | ⬜ |
| Heat-pipe relay | Infrastructure — Magma light | ⬜ |

## 4. Camp & colony props

| Asset | Role | Status |
|---|---|---|
| Stockpile chest | Ore/goods store marker | ✅ treasure-chest |
| Cot / bedroll | Delver beds | ✅ catalogued and in frontend use 2026-11-11 |
| Mushroom plot cluster | Farm plots | ✅ mushroom-cluster |
| Converter forge | Ore → goods station | ⬜ |
| Chandlery / rendering bench | Tallow & oil station | ⬜ |
| Charcoal kiln | Torch fuel station | ⬜ |
| Herbalist bench + drying rack | Medicine / spore care | ⬜ |
| Tailor bench | Masks & gear crafting | ⬜ |
| Sealed food store | Fungal-band food storage | ⬜ |
| The Deep Ledger | Lectern/monument — the colony's record, in-world | ⬜ |
| Surface gate | Entrance structure where recruits arrive | ⬜ |
| Timber support set | Shallows gate — beams/props vs cave-ins | ⬜ |
| Ventilation pieces | Shallows gate — shaft + baffles | ⬜ |
| Camp clutter set | Crates, barrels, sacks, woodpile | ⬜ (fallen-log + stump ✅ as dressing) |

## 5. Faces & resources (what gets mined)

| Asset | Role | Status |
|---|---|---|
| Ore face rock | Veined rock block for faces | ⬜ (frontend: coloured cube) |
| Fungal node | Glowing mineable growth | ⬜ (frontend: coloured cube) |
| Crystal cluster | Crystal Dark resource face | ⬜ |
| Carried-load props | Ore chunk / oil flask in hands while hauling | ⬜ |

## 6. Band dressing & gate kit pieces

| Band | Assets | Status |
|---|---|---|
| Shallows | Stalactite/stalagmite set, rubble | ⬜ (boulder ✅) |
| Fungal Reaches | Giant mushrooms, spore pods, fungal mats | ⬜ (mushroom-cluster ✅ at small scale) |
| Drowned Galleries | Pump, drain grate, air bell, pipe runs | ⬜ |
| Crystal Dark | Crystal formations, lens posts, route markers, anchor points | ⬜ |
| Magma Roots | Basalt columns, heat pipes, emergency plugs, cooling vents | ⬜ |

## 7. Items & UI art (2D / small props)

Store/job icons (ore, goods, food, fungal oil, mask), job icons
(miner/hauler/farmer/herbalist), the Deep Ledger UI motif, band
banners for the five depths, and a title/key-art piece. ⬜ all —
drawn or generated 2D, not the 3D pipeline.

## 8. Not pipeline work (listed so it isn't lost)

- **VFX:** lantern glow falloff sprites, spore motes, drip/splash,
  lava glow, first-light flare — engine-side.
- **Audio:** cave ambience per band, lantern hiss, mining/hauling
  foley, creature calls, the Ledger sting — recorded/synthesised,
  no current pipeline.
- **Skybox/surface:** the surface world above the gate is a menu
  backdrop at most; the game lives underground.

## Totals

~55 pipeline assets: 10 character-side, 7 creatures, 9 light,
14 camp, 4 faces/loads, ~11 band kit/dressing — of which **8 are
catalogued and in use today** (delver, oil lantern, cot, stockpile
chest, mushroom cluster, fallen-log, stump, gloam-lurker), and
the rest are designed and waiting.
