# LivingWorld v0.3 Addendum — Dungeons, Dungeon Lords, and the Hollow

## Status

This document is a **normative addendum to the post-v0.2 `ROADMAP.md`** and should be treated as part of the v0.3 World Depth roadmap.

It changes one important roadmap assumption:

- **backend dungeon simulation is no longer deferred until after the World Depth Readiness Gate**;
- visual dungeon construction, encounter design, player combat, loot presentation, and Unreal dungeon gameplay remain deferred.

The simulation should know that dungeons exist and affect the world long before a player can physically enter one.

---

# 1. Setting Term — The Hollow

The hostile world-scale force previously described informally as "the dark" should use the setting name:

> **The Hollow**

The Hollow is not simply darkness, a race, or a single monster faction. It is a force that works against continuity, civilization, memory, structure, and ordered life.

Its influence can manifest through:

- corrupted places,
- forbidden magic,
- cults,
- monsters,
- undead,
- warped ecosystems,
- cursed artifacts,
- fallen rulers,
- Dungeon Lords,
- reality-distorting anomalies.

This gives hostile forces a shared cosmological allegiance without requiring every Dungeon Lord, cult, monster, or dungeon to look or behave the same.

The Hollow should remain partially mysterious. The deterministic simulation needs to understand its rules, but the setting does not need to immediately explain its ultimate origin to players.

---

# 2. What Makes a Dungeon a Dungeon

Not every cave, ruin, mine, crypt, fortress, or underground structure should count as a true Dungeon.

A **Dungeon** is a persistent hostile world entity that has become an anchor, stronghold, wound, or instrument of the Hollow.

Examples of locations that can become Dungeons:

- abandoned mines,
- ruined fortresses,
- ancient temples,
- collapsed cities,
- forgotten tomb complexes,
- magical laboratories,
- deep caverns,
- corrupted forests,
- sewer networks,
- old military bunkers/keeps appropriate to the setting,
- newly created lairs built by a Dungeon Lord,
- sites of magical disaster,
- places where a cult successfully opens a breach.

A normal ruin can exist for centuries without being a Dungeon.

A Dungeon is distinguished by active hostile organization and world influence.

---

# 3. Dungeon Entity Model

Each Dungeon should have a persistent unique ID and structured state.

Suggested fields include:

```text
Dungeon
- id
- name
- origin_type
- location / region / settlement proximity
- discovered_state
- created_at
- current_lord_id
- allegiance = HOLLOW
- threat_level
- corruption_level
- secrecy
- fortification
- depth / complexity tier
- population / occupants
- monster groups
- cultist population
- prisoner population
- stored resources
- food / supply
- wealth / treasure reserve
- magical power reserve
- influence radius
- linked sites
- known entrances
- activity state
- history event IDs
- status
```

Possible statuses:

- dormant,
- stirring,
- active,
- expanding,
- besieged,
- leaderless,
- shattered,
- sealed,
- cleansed,
- reclaimed by the Hollow.

A Dungeon should continue existing historically after destruction or cleansing.

---

# 4. Dungeon Origins

Dungeons should have causal origins rather than simply appearing from a random spawn table.

Possible origins include:

## 4.1 Fallen settlement

```text
War / famine / plague / abandonment
-> settlement collapses
-> ruins remain
-> Hollow influence grows
-> hostile inhabitants occupy site
-> Dungeon forms
```

## 4.2 Corrupted resource site

```text
Mine discovers magical deposit
-> unsafe extraction
-> magical disaster
-> workers disappear / mutate / flee
-> site becomes isolated
-> Dungeon forms
```

## 4.3 Cult-created breach

```text
Religious or political unrest
-> cult gains followers
-> hidden ritual site established
-> ritual succeeds
-> Hollow influence anchors
-> Dungeon forms
```

## 4.4 Dungeon Lord construction

A sufficiently powerful Dungeon Lord can deliberately establish a new stronghold in strategic territory.

## 4.5 Ancient dormant site

World generation may include a small number of old sealed sites that predate current kingdoms.

They should have histories, reasons for remaining sealed, and conditions that can awaken them.

---

# 5. Dungeon Lords

Dungeon Lords are persistent named actors and strategic agents of the Hollow.

They are not merely final bosses waiting in a room.

A Dungeon Lord should participate in the world simulation even when no player is nearby.

Possible Dungeon Lord archetypes include:

- fallen noble,
- necromancer,
- warlock,
- ancient monster,
- undead ruler,
- corrupted priest,
- demon-like entity unique to the setting,
- sorcerous construct,
- monster chieftain,
- corrupted dragon or equivalent major creature,
- former hero consumed by the Hollow.

Archetype should affect strategy but not completely determine personality or goals.

---

# 6. Dungeon Lord Agent State

Suggested persistent Dungeon Lord data:

```text
DungeonLord
- npc/entity id
- name
- origin
- ancestry/species where applicable
- age / timeless state
- dungeon_id
- traits
- skills
- powers
- ambitions
- preferred strategy
- risk tolerance
- hatred / rivalries
- memories
- known enemies
- lieutenants
- cult connections
- resource needs
- military strength
- magical strength
- secrecy preference
- expansion preference
- corruption affinity
- current plans
- succession conditions
```

Dungeon Lords should use deterministic utility/goal-based AI like other authoritative actors.

No LLM call should be required to choose their authoritative actions.

---

# 7. Dungeon Lord Goals

Possible strategic goals:

- survive,
- remain hidden,
- gather magical power,
- recruit followers,
- acquire corpses,
- acquire prisoners,
- steal resources,
- corrupt a settlement,
- destroy a religious site,
- sabotage a trade route,
- assassinate a ruler,
- manipulate a faction,
- cause a war,
- weaken a border region,
- recover an artifact,
- awaken another Dungeon,
- create a new Dungeon,
- conquer nearby territory,
- establish cult cells,
- spread fear,
- destroy historical records,
- kill a rival Dungeon Lord,
- achieve a unique long-term Hollow objective.

Different Lords should pursue different combinations.

---

# 8. Dungeon Growth

Dungeons should develop over time.

A Dungeon can become stronger by acquiring:

- population,
- monsters,
- cultists,
- wealth,
- food,
- prisoners,
- magical resources,
- artifacts,
- construction materials,
- strategic knowledge.

Example progression:

```text
Dormant crypt
-> cult occupation
-> first disappearances
-> local fear rises
-> Dungeon Lord takes control
-> raids begin
-> trade road becomes unsafe
-> nearby village loses population
-> kingdom sends troops
-> troops fail
-> Dungeon gains equipment and prisoners
-> influence expands
-> regional crisis begins
```

Growth should create visible external consequences.

---

# 9. Dungeon Economy and Logistics

Dungeons should not receive infinite troops and resources from nowhere.

Depending on type, they may need:

- food,
- bodies,
- magical energy,
- metal,
- weapons,
- labor,
- livestock,
- money,
- captives.

They can obtain resources through:

- raids,
- cult donations,
- underground production,
- corrupted resource nodes,
- theft,
- black markets,
- tribute,
- alliances with criminal organizations,
- trade with other hostile entities.

This lets kingdoms weaken a Dungeon by isolating it, not only by storming it directly.

---

# 10. Corruption / Hollow Influence

Track an explicit but bounded **Hollow influence** value at relevant sites or regions.

Influence can increase through:

- active Dungeons,
- magical disasters,
- cult activity,
- cursed artifacts,
- successful raids,
- mass death,
- prolonged abandonment,
- Dungeon Lord rituals.

Influence can decrease through:

- destroying or sealing a Dungeon,
- strong local institutions,
- religious/magical countermeasures,
- resettlement,
- cleansing rituals,
- rebuilding infrastructure,
- long periods of security.

Influence should affect systems rather than merely tinting a map.

Possible effects:

- migration pressure,
- disease or magical anomalies,
- monster activity,
- lower trade security,
- lower settlement stability,
- cult recruitment,
- fear/reputation,
- resource corruption,
- altered local ecology,
- increased chance of new hostile sites.

Avoid automatic irreversible snowballing. Civilizations must be capable of pushing the Hollow back.

---

# 11. Interaction with Existing World Systems

## Politics

Dungeon activity can:

- damage ruler legitimacy,
- strengthen military factions,
- create religious movements,
- trigger emergency laws,
- cause governors to rebel if abandoned by the crown,
- create accusations of collaboration.

## Economy

Dungeons can:

- block roads,
- raid caravans,
- destroy farms,
- occupy mines,
- increase security costs,
- create scarcity,
- create dangerous but valuable resource opportunities.

## Migration

Threatened populations can flee from Dungeon influence.

## Religion

Religious institutions can become major opponents, collaborators, victims, or ideological interpreters of the Hollow.

## Crime

Criminal organizations may smuggle goods to Dungeons, sell information, traffic captives, or fight them when business is threatened.

## Warfare

Kingdom armies can siege or contain Dungeons.

Dungeon forces can raid settlements and, at high power, conduct strategic attacks.

## Culture

Generations living beside a major Dungeon may develop traditions, taboos, military customs, heroes, festivals, fears, or specialized institutions because of it.

## History

Dungeon events must be first-class historical events with causal links.

---

# 12. Dungeon Forces

A Dungeon should have an abstract strategic population before any Unreal creature is spawned.

Possible force categories:

- monsters,
- undead,
- cultists,
- corrupted humanoids,
- constructs,
- summoned entities,
- beasts,
- elite lieutenants.

Track enough information to determine:

- raid strength,
- defense strength,
- attrition,
- supply demand,
- replacement rate,
- special capabilities.

Do not individually simulate every creature while the Dungeon is off-screen.

---

# 13. Lieutenants and Succession

Dungeon Lords should not always be single points of failure.

Powerful Dungeons can contain persistent lieutenants.

If a Lord dies:

```text
Lord dies
-> power vacuum
-> Dungeon destabilizes
-> lieutenants compete
-> Dungeon may fragment, collapse, go dormant, or gain a new Lord
```

A new Lord may:

- inherit the Dungeon,
- change its strategy,
- purge rivals,
- move the stronghold,
- become weaker or stronger than the predecessor.

This allows Dungeons to have dynastic/history-like continuity.

---

# 14. Dungeon Relationships

Dungeon Lords should not automatically cooperate just because all serve the Hollow.

They can:

- ally,
- feud,
- compete for artifacts,
- raid one another,
- exchange servants,
- share cult networks,
- betray one another,
- recognize a stronger Lord,
- form temporary coalitions against kingdoms.

This prevents the Hollow from behaving like one perfectly coordinated hive mind.

---

# 15. Discovery and Knowledge

Kingdoms and settlements should not automatically know a Dungeon exists.

Discovery states can include:

- unknown,
- rumored,
- suspected,
- located,
- mapped,
- fully understood.

Knowledge can come from:

- survivors,
- scouts,
- merchants,
- missing-person patterns,
- religious visions/rituals where appropriate,
- captured cultists,
- military reconnaissance,
- adventurers later.

False or outdated information should be possible.

---

# 16. Dungeon Threat and Regional Response

Threat should be calculated from real conditions such as:

- Dungeon population,
- Lord power,
- supplies,
- recent raids,
- proximity to population centers,
- strategic position,
- corruption/influence,
- secrecy,
- kingdom response capacity.

Possible responses:

- ignore,
- investigate,
- patrol,
- fortify nearby settlement,
- blockade,
- sponsor hunters/adventurers later,
- send army,
- negotiate under rare circumstances,
- evacuate region,
- conduct cleansing campaign.

Political disagreement over the response should be possible.

---

# 17. Raids and External Actions

Dungeons need a strategic action system.

Possible actions:

- raid farm,
- raid caravan,
- abduct inhabitants,
- steal artifact,
- attack patrol,
- corrupt resource node,
- sabotage bridge,
- infiltrate settlement,
- establish cult cell,
- assassinate target,
- spread magical contamination,
- scout kingdom defenses,
- reinforce another Dungeon,
- found satellite lair.

These actions should produce structured events and consequences.

---

# 18. Dungeon Defeat

Dungeon defeat should have multiple possible outcomes.

## Shattered

Military power destroyed but corruption remains.

## Sealed

Access is contained; Dungeon may awaken later.

## Cleansed

Hollow influence removed or heavily reduced.

## Occupied

Kingdom, order, cult, or other organization takes the site.

## Abandoned

Lord leaves and relocates.

## Reclaimed

A defeated Dungeon later returns under a new Lord.

Defeating a Lord does not automatically delete centuries of history from the location.

---

# 19. Dungeon Rewards Before Loot Systems

Before a player loot system exists, Dungeon value can be represented strategically through:

- recovered treasury,
- artifacts,
- rare resources,
- rescued captives,
- restored trade routes,
- reclaimed mines,
- political legitimacy,
- religious prestige,
- military reputation,
- historical discoveries.

These give civilizations a reason to confront Dungeons beyond an abstract good-versus-evil meter.

---

# 20. Dynamic World Problems

Dungeon state should feed the roadmap's world-problem/quest-seed layer.

Examples:

```text
Caravans disappearing on the north road
Village livestock taken at night
Missing miners
Cult recruitment in poor district
Ancient sealed crypt showing magical activity
Refugees arriving from frontier hamlets
Army patrol failed to return
Dungeon Lord seeking a lost artifact
Fort commander requesting reinforcements
Religious order requesting supplies for containment
```

The problem should disappear, transform, or escalate when the underlying simulation state changes.

---

# 21. Historical Examples

A Dungeon should generate explainable histories such as:

```text
Year 73
Mine of Silverdeep suffers magical collapse.

Year 76
Survivors abandon the lower valley.

Year 81
Cult of the Broken Star occupies the mine.

Year 84
Vael Mordryn becomes Dungeon Lord of Silverdeep.

Year 86
Raids reduce traffic on the East Road by 31%.

Year 88
Food prices rise in two frontier towns.

Year 89
The crown creates the March Wardens.

Year 94
A royal campaign fails to clear Silverdeep.

Year 103
A second campaign kills Vael Mordryn.

Year 104
His lieutenant Sereth claims the Dungeon.

Year 117
Silverdeep is finally sealed.

Year 143
Earthquake damage breaks the seal.
```

That is the level of persistence and causality the Dungeon system should eventually support.

---

# 22. Multi-Seed Validation Metrics

Add Dungeon metrics to long-horizon validation:

- Dungeons created,
- Dungeons active,
- Dungeons destroyed/sealed/cleansed,
- average Dungeon lifespan,
- Dungeon Lords created/killed/replaced,
- raids per century,
- settlements damaged by Dungeons,
- migrations caused by Dungeon threats,
- trade losses caused by Dungeons,
- maximum Hollow influence,
- cult organizations created,
- kingdoms that launch containment campaigns,
- regional recoveries after Dungeon defeat.

Balance should avoid both extremes:

- a world where every settlement is eventually consumed,
- a world where Dungeons never matter.

---

# 23. World Depth Readiness Additions

The World Depth Readiness Gate must now also require:

## Dungeon integrity

- Dungeon references remain structurally valid,
- defeated Dungeons remain historically queryable,
- Dungeon Lord succession cannot create broken ownership,
- Dungeon resources do not appear from nowhere,
- influence values remain bounded.

## Causal impact

- at least some seeds produce meaningful Dungeon-driven regional crises,
- civilizations can successfully contain or destroy Dungeons,
- Dungeons can cause trade, migration, political, religious, and military consequences,
- not every seed experiences civilization-threatening escalation,
- Dungeon outcomes can be reconstructed from history.

## Long-term balance

- the Hollow cannot monotonically and inevitably consume the map,
- civilization cannot trivially eliminate all Dungeon threats immediately,
- new Dungeons can emerge from historical conditions,
- old Dungeons can disappear, sleep, return, or change leadership.

---

# 24. Recommended Roadmap Placement

Insert backend Dungeon development after the supporting world systems are mature enough to give Dungeons meaningful inputs and consequences.

Recommended revised implementation order around the latter half of v0.3:

```text
Slice 13 Diplomacy 2.0 + typed claims/treaties
Slice 14 Warfare 2.0 + war economy + occupation policy
Slice 15 Kingdom lifecycle + rebellion/secession/dissolution
Slice 16 Strategic geography + provinces/chokepoints
Slice 17 Organizations + guilds/orders/cults
Slice 18 Dungeons + Hollow influence + Dungeon entity lifecycle
Slice 19 Dungeon Lords + strategic agent AI + raids + succession
Slice 20 Historical causality + political/dungeon map replay
Slice 21 Dynamic world problems / quest seeds
Slice 22 Multi-seed 200-year validation + performance hardening
Slice 23 Dashboard world-observatory + Dungeon observatory pass
Slice 24 World Depth Readiness review
```

Earlier slices should include schema hooks where useful, but full Dungeon behavior should wait until economy, logistics, politics, NPCs, religion, warfare, geography, and organizations can interact with it.

---

# 25. Unreal Boundary

The following remain **post-readiness gameplay tasks**:

- generating physical dungeon layouts,
- rooms/corridors,
- encounter spawning,
- traps,
- Unreal navigation,
- combat AI,
- boss fights,
- player loot,
- dungeon matchmaking/instancing decisions,
- visual corruption effects,
- animation and VFX.

The server-side simulation should already be able to answer:

- Where is this Dungeon?
- Why did it form?
- Who rules it?
- What does the Lord want?
- What resources does it control?
- Who knows about it?
- What settlements has it harmed?
- What raids has it launched?
- What political response has it caused?
- Who previously ruled it?
- Has it ever been defeated?
- Why is it dangerous right now?

Only then should Unreal turn that persistent world entity into a place the player can physically enter.

---

# 26. Definition of Success

The Dungeon system succeeds when a Dungeon is not simply:

> "a level full of monsters."

It should instead be possible to inspect a Dungeon after 100+ simulated years and explain:

- how it was created,
- why it survived,
- who ruled it,
- how leadership changed,
- where its resources came from,
- which settlements it harmed,
- which cultures and institutions formed in response,
- which wars or political crises it influenced,
- why campaigns against it succeeded or failed,
- and what consequences remained after it was defeated.

A Dungeon should be a **historical actor in the world** before it ever becomes a gameplay level.