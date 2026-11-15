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
| The Frontier Bearer (player) | Rigged biped with the great lantern; idle/walk/run + plant-light, carve swing | ✅ catalogued 2026-11-13 as frontier-bearer (clips idle/walk/run/plant/swing; arm-separation gates passed) — not yet in frontend use: no player-avatar slot exists (co-op tint variants still ⬜) |
| Miner kit — pickaxe + helmet lamp | Hand/back props, attachable | ✅ catalogued 2026-11-13 (`miner-pickaxe` aaba8c8e…, `miner-helmet-lamp` 389dded4…; unrigged props, no frontend equipment slot yet) |
| Hauler kit — carry sack / ore basket | Back prop | ✅ catalogued 2026-11-13 (`hauler-ore-basket` 076c73f4…; built as the ore-basket form, unrigged prop, no frontend equipment slot yet) |
| Farmer kit — sickle + pouch | Hand/belt props | ✅ catalogued 2026-11-13 (`farmer-sickle` 0c7a2177…, `farmer-pouch` effbd495…; unrigged props, no frontend equipment slot yet) |
| Herbalist kit — herb bundle + satchel | Hand/shoulder props | ✅ catalogued 2026-11-13 (`herbalist-herb-bundle` 0aad75f6…, `herbalist-satchel` 5ae94948…; unrigged props, no frontend equipment slot yet) |
| Spore mask | Worn face prop (equipped visual for the S5 gate) | ✅ catalogued 2026-11-13 (`spore-mask` adf3774f…; unrigged prop, no frontend equipment slot yet) |
| Harness + rope | Worn prop (Crystal Dark gate) | ✅ catalogued 2026-11-13 (`harness-and-rope` c88cebdf…; unrigged prop, no frontend equipment slot yet) |
| Quiet gear — padded wraps | Worn prop set (Crystal Dark gate) | ✅ catalogued 2026-11-13 (`quiet-gear-boot-wraps` 34b0a84e…, `quiet-gear-arm-wraps` d2186ec0…; unrigged props, no frontend equipment slot yet) |
| Cooling gear — insulated suit pieces | Worn prop set (Magma gate) | ✅ catalogued 2026-11-13 (`cooling-gear-vest` a08014fa…, `cooling-gear-gauntlets` 5a954120…; unrigged props, no frontend equipment slot yet) |

## 2. Creatures

| Asset | Spec | Status |
|---|---|---|
| Gloam rat | Rigged quadruped, small; idle/walk/run + bite lunge | ✅ catalogued 2026-11-13 as gloam-rat (clips idle/walk/run/bite — bite is a new builder signature; leg-separation gates passed) and in frontend use — critter rendering is kind-aware since 2026-11-13 |
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
| Torch on a stand | Tier 0 — torches/charcoal | ✅ catalogued 2026-11-13 (`torch-on-a-stand` bcba2c67…; unrigged prop — not yet in frontend use: `make_lantern_node` renders the Tier-1 prop for every tier and the placement UI only places tier 1, so per-tier prop selection lands with the slice that makes torches placeable) |
| Oil lantern on a post | Tier 1 — the colony standard | ✅ catalogued and in frontend use 2026-11-11 (OmniLight + emissive flame marker kept) |
| Fungal-oil lantern | Tier 2 — spore-repellent glow | ✅ catalogued 2026-11-13 (`fungal-oil-lantern` aebb0ea6…; unrigged prop — not yet in frontend use: per-tier prop selection lands with the slice that makes tier-2 placement available, see the Tier 0 note) |
| Sealed pressure lantern | Tier 3 — waterproof (Drowned) | ✅ catalogued 2026-11-14 (`sealed-pressure-lantern` 02235185…; unrigged prop — not yet in frontend use: per-tier prop selection lands with the slice that makes tier-3 placement available, see the Tier 0 note) |
| Crystal-heart lantern | Tier 4 — focused beam (Crystal Dark) | ✅ catalogued 2026-11-14 (`crystal-heart-lantern` 0b3894f5…; unrigged prop — not yet in frontend use: per-tier prop selection lands with the slice that makes tier-4 placement available, see the Tier 0 note) |
| Thermal lamp | Tier 5 — vent-fed (Magma) | ✅ catalogued 2026-11-14 (`thermal-lamp` 99fef953…; unrigged prop — not yet in frontend use: per-tier prop selection lands with the slice that makes tier-5 placement available, see the Tier 0 note) |
| Piped light-spine segment | Infrastructure — lit main routes | ✅ catalogued 2026-11-14 (`piped-light-spine-segment` 572ff8f8…; unrigged prop — not yet in frontend use: no light-spine placement exists in the frontend yet, lands with the infrastructure slice that makes spine routes placeable) |
| Crystal relay | Infrastructure — light relay | ✅ catalogued 2026-11-14 (`crystal-relay` d0bfd195…; unrigged prop — not yet in frontend use: no relay placement exists in the frontend yet, lands with the infrastructure slice that makes relay routes placeable) |
| Heat-pipe relay | Infrastructure — Magma light | ✅ catalogued 2026-11-14 (`heat-pipe-relay` 3eb947d3…; unrigged prop — not yet in frontend use: no relay placement exists in the frontend yet, lands with the infrastructure slice that makes relay routes placeable) |
| Cart | Infrastructure — hauling | ✅ catalogued 2026-11-14 (`cart` ae07e9a6…; unrigged prop — not yet in frontend use: no cart/hauling placement exists in the frontend yet, lands with the infrastructure slice that makes hauling routes placeable) |

## 4. Camp & colony props

| Asset | Role | Status |
|---|---|---|
| Stockpile chest | Ore/goods store marker | ✅ treasure-chest |
| Cot / bedroll | Delver beds | ✅ catalogued and in frontend use 2026-11-11 |
| Mushroom plot cluster | Farm plots | ✅ mushroom-cluster |
| Converter forge | Ore → goods station | ✅ catalogued 2026-11-15 (`converter-forge` fef3e81b…; unrigged prop — not yet in frontend use: no converter/station placement exists in the frontend yet, lands with the station slice that makes workstations placeable) |
| Chandlery / rendering bench | Tallow & oil station | ✅ catalogued 2026-11-15 (`chandlery-bench` 700d1c9e…; unrigged prop — not yet in frontend use: no station placement exists in the frontend yet, lands with the station slice that makes workstations placeable) |
| Charcoal kiln | Torch fuel station | ✅ catalogued 2026-11-15 (`charcoal-kiln` 4106b836…; unrigged prop — not yet in frontend use: no station placement exists in the frontend yet, lands with the station slice that makes workstations placeable) |
| Herbalist bench + drying rack | Medicine / spore care | ✅ catalogued 2026-11-15 (`herbalist-bench` 42e19d33…; unrigged prop — not yet in frontend use: no station placement exists in the frontend yet, lands with the station slice that makes workstations placeable) |
| Tailor bench | Masks & gear crafting | ✅ catalogued 2026-11-15 (`tailor-bench` 632f4cf5…; unrigged prop — not yet in frontend use: no station placement exists in the frontend yet, lands with the station slice that makes workstations placeable) |
| Sealed food store | Fungal-band food storage | ✅ catalogued 2026-11-15 (`sealed-food-store` e210e454…; unrigged prop — not yet in frontend use: no station placement exists in the frontend yet, lands with the station slice that makes workstations placeable) |
| The Deep Ledger | Lectern/monument — the colony's record, in-world | ✅ catalogued 2026-11-15 (`deep-ledger` 7f0a50a0…; unrigged prop — not yet in frontend use: no station placement exists in the frontend yet, lands with the station slice that makes workstations placeable) |
| Surface gate | Entrance structure where recruits arrive | ✅ catalogued 2026-11-15 (`surface-gate` 954f7b06…; unrigged prop — not yet in frontend use: no station placement exists in the frontend yet, lands with the station slice that makes workstations placeable) |
| Timber support set | Shallows gate — beams/props vs cave-ins | ✅ catalogued 2026-11-15 (`timber-support-set` 50fc438a…; unrigged prop — not yet in frontend use: no support-prop placement exists in the frontend yet, lands with the slice that makes gate props placeable) |
| Ventilation pieces | Shallows gate — shaft + baffles | ✅ catalogued 2026-11-15 (`ventilation-pieces` 0889b35a…; unrigged prop — not yet in frontend use: no ventilation placement exists in the frontend yet, lands with the slice that makes gate props placeable) |
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
