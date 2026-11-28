//! AI civilization planning (design §6.5, §2 "AI civs re-plan").
//!
//! Each AI civilization re-plans once per month, on the settlement
//! boundary, through the *same* public command surface the player
//! (and the S1 scripted policy) uses — `dispatch_ship_for`,
//! `claim_system_for`, `build_ship_for`, and friends. There is no AI
//! back door: same costs, same ranges, same fog of war (an AI only
//! ever acts on systems it has itself surveyed), same failure modes.
//! Planning is a pure function of campaign state — no wall clock, no
//! hidden randomness — so catch-up equivalence (§11.1) holds with AI
//! races active exactly as it did solo.
//!
//! The planner mirrors the S1 scripted policy's priorities, scoped
//! to one civilization and tinted by its personality: expansion
//! lowers the treasury reserve kept back before building colony
//! ships and claiming; aggression decides whether it contests
//! foreign claims it covets.
//!
//! S5 adds the war step (§6.4): an AI at war builds warships,
//! sails them at the enemy colonies it has itself surveyed, and
//! invades through the same command the player uses; exhaustion
//! sues it to the peace table; and declarations follow stated
//! gates — aggression, opinion, a grievance (or hatred deep
//! enough to need none), honour's demand for a grievance, and a
//! fog-honest strength comparison (only enemy ships at systems
//! the declarer has surveyed count). The AI builds no gates and
//! terraforms nothing in S5 — recorded in the handoff.

use crate::catalog::Galaxy;
use crate::race::Personality;
use crate::state::{
    Campaign, DealOutcome, PeaceTerms, Purpose, ShipKind, ShipState, Specialization, TreatyKind,
    CLAIM_COST_CREDITS, PLAYER_CIV,
};

/// Minimum habitability an AI will claim or colonize (design §6.2's
/// placement floor, reused as the expansion floor).
const MIN_CLAIM_HABITABILITY: f64 = 40.0;
/// Habitability at which a foreign-held system becomes worth a
/// dispute for an aggressive civilization.
const CONTEST_HABITABILITY: f64 = 55.0;
/// Alloys a colony keeps in reserve; builds start above this.
const ALLOY_BUILD_RESERVE: f64 = 90.0;

/// Run one month of planning for civilization `civ_id`. Called from
/// the core's daily step on settlement days only.
pub fn plan_month(campaign: &mut Campaign, galaxy: &Galaxy, civ_id: u32) {
    let Some(civ) = campaign.civ(civ_id) else {
        return;
    };
    if !civ.is_ai() {
        return;
    }
    let personality = civ.personality.unwrap_or_default();
    let expansion = personality.expansion;

    refuel_own_ships(campaign, civ_id);
    assign_specializations(campaign, civ_id);
    build_ships(campaign, civ_id, expansion);
    claim_systems(campaign, civ_id, expansion);
    // S4 diplomacy runs before contesting: a pact signed this
    // month already binds this month's claims.
    diplomacy_step(campaign, galaxy, civ_id, personality);
    // S5 war: declarations, warship building, fleet movements,
    // invasions, and peace feelers — after diplomacy, so a
    // settlement reached this month is not declared over in the
    // same breath.
    war_step(campaign, galaxy, civ_id, personality);
    contest_claims(campaign, civ_id, personality.aggression);
    // One shared return-cost field for this month's dispatching,
    // keyed to the surveyor design's legs and tank.
    let surveyor_design = campaign
        .designs()
        .iter()
        .find(|d| d.kind == ShipKind::Surveyor)
        .cloned();
    let field = match surveyor_design {
        Some(design) => return_cost_field(
            campaign,
            galaxy,
            civ_id,
            design.range_ly(),
            design.fuel_per_ly,
            design.tank_capacity,
        ),
        None => Default::default(),
    };
    dispatch_idle_ships(campaign, galaxy, civ_id, &field);
}

/// Top up (or rescue) this civilization's ships sitting at its own
/// colonies. A stranded ship with fuel available resumes its orders
/// through the core's refuel path, exactly like a player's.
fn refuel_own_ships(campaign: &mut Campaign, civ_id: u32) {
    for ship_id in campaign.ships_of(civ_id) {
        let Some(ship) = campaign.ship(ship_id) else {
            continue;
        };
        let needs_fuel = match ship.state {
            ShipState::StrandedAtSystem { .. } => true,
            ShipState::AtSystem { .. } => {
                let tank = campaign
                    .design(ship.design_idx)
                    .map(|d| d.tank_capacity)
                    .unwrap_or(0.0);
                // 90%, not the scripted policy's 98%: the planner
                // runs monthly, and topping up the last trickle
                // every month floods the event log with refuels
                // (thousands over a long game) for no real gain —
                // the prudence check prices departures on the fuel
                // actually aboard either way.
                ship.fuel < tank * 0.9
            }
            _ => false,
        };
        if needs_fuel {
            // Errors (no colony here, empty stock) just mean "not
            // this month"; planning never propagates failures.
            let _ = campaign.refuel_ship_for(civ_id, ship_id);
        }
    }
}

/// Mirror of the scripted policy's specialization heuristic, scoped
/// to this civilization's mature colonies.
fn assign_specializations(campaign: &mut Campaign, civ_id: u32) {
    for system in campaign.colonies_of(civ_id) {
        let Some(state) = campaign.system(system) else {
            continue;
        };
        let Some(colony) = &state.colony else {
            continue;
        };
        if colony.development < 3 || colony.specialization.is_some() {
            continue;
        }
        let Some(profile) = campaign.known_profile(civ_id, system) else {
            continue;
        };
        let spec = if profile.fuel_trait >= 1.1 {
            Specialization::Refinery
        } else if profile.industry_trait >= 1.1 {
            Specialization::Industrial
        } else {
            Specialization::Agricultural
        };
        let _ = campaign.assign_specialization_for(civ_id, system, spec);
    }
}

/// Build surveyors up to a small working fleet (which grows
/// slightly as the civilization spreads — more colonies, more
/// frontier to cover), then colony ships while the treasury stays
/// above a personality-scaled reserve.
fn build_ships(campaign: &mut Campaign, civ_id: u32, expansion: f64) {
    let designs = campaign.designs().to_vec();
    let (surveyor_idx, colony_idx) = (0u32, 1u32);
    if designs.len() < 2 {
        return;
    }
    let reserve = 220.0 - 140.0 * expansion;
    let colony_count = campaign.colonies_of(civ_id).len();
    let surveyor_target = 2 + usize::from(colony_count >= 6) + usize::from(colony_count >= 12);
    for system in campaign.colonies_of(civ_id) {
        let Some(state) = campaign.system(system) else {
            continue;
        };
        let Some(colony) = &state.colony else {
            continue;
        };
        if !colony.construction_queue.is_empty()
            || colony.alloys_stock < ALLOY_BUILD_RESERVE + designs[0].alloys_cost()
        {
            continue;
        }
        let my_ships = campaign.ships_of(civ_id);
        let surveyors = my_ships
            .iter()
            .filter(|id| {
                campaign
                    .ship(**id)
                    .map(|s| designs[s.design_idx as usize].kind == ShipKind::Surveyor)
                    .unwrap_or(false)
            })
            .count();
        let colony_ships = my_ships
            .iter()
            .filter(|id| {
                campaign
                    .ship(**id)
                    .map(|s| designs[s.design_idx as usize].kind == ShipKind::Colony)
                    .unwrap_or(false)
            })
            .count();
        let want = if surveyors < surveyor_target {
            Some(surveyor_idx)
        } else if colony_ships == 0
            && campaign.credits_for(civ_id) >= designs[1].credits_cost() + reserve
        {
            Some(colony_idx)
        } else {
            None
        };
        if let Some(design_idx) = want {
            let _ = campaign.build_ship_for(civ_id, system, design_idx);
        }
    }
}

/// Claim this civilization's best surveyed, unclaimed systems while
/// the treasury stays above the claim reserve.
fn claim_systems(campaign: &mut Campaign, civ_id: u32, expansion: f64) {
    let reserve = 160.0 - 100.0 * expansion;
    let mut candidates: Vec<(f64, u32)> = campaign
        .surveyed_systems_of(civ_id)
        .into_iter()
        .filter_map(|system| {
            let state = campaign.system(system)?;
            if state.claimed_by.is_some() || state.colony.is_some() {
                return None;
            }
            let profile = campaign.known_profile(civ_id, system)?;
            if profile.habitability_percent < MIN_CLAIM_HABITABILITY {
                return None;
            }
            Some((profile.habitability_percent, system))
        })
        .collect();
    // Best first; system id breaks habitability ties so the order is
    // total and deterministic.
    candidates.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(&b.1)));
    for (_, system) in candidates {
        if campaign.credits_for(civ_id) < CLAIM_COST_CREDITS + reserve {
            break;
        }
        let _ = campaign.claim_system_for(civ_id, system);
    }
}

/// An aggressive civilization contests at most one coveted foreign
/// claim per month: best surveyed system held by someone else, with
/// no colony on it yet and no dispute of its own already open.
fn contest_claims(campaign: &mut Campaign, civ_id: u32, aggression: f64) {
    if aggression < 0.55 {
        return;
    }
    let already: Vec<u32> = campaign
        .disputes()
        .iter()
        .filter(|d| d.challenger == civ_id)
        .map(|d| d.system)
        .collect();
    let mut candidates: Vec<(f64, u32)> = campaign
        .surveyed_systems_of(civ_id)
        .into_iter()
        .filter_map(|system| {
            let state = campaign.system(system)?;
            let holder = state.claimed_by?;
            if holder == civ_id || state.colony.is_some() || already.contains(&system) {
                return None;
            }
            let profile = campaign.known_profile(civ_id, system)?;
            if profile.habitability_percent < CONTEST_HABITABILITY {
                return None;
            }
            Some((profile.habitability_percent, system))
        })
        .collect();
    candidates.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(&b.1)));
    if let Some((_, system)) = candidates.first() {
        let _ = campaign.contest_claim_for(civ_id, *system);
    }
}

/// The return-cost field for one civilization: for every system
/// within useful reach, the fuel cost of the cheapest hop-by-hop
/// route back to one of its colonies (multi-source Dijkstra over
/// the star graph, each hop within `range_ly`, costs capped at
/// `cap_cost` — beyond a full tank, the exact number no longer
/// matters). Computed once per civilization per month and shared
/// by all its surveyors; a system missing from the map is treated
/// as "cannot come back", which for a surveyor means "do not go".
fn return_cost_field(
    campaign: &mut Campaign,
    galaxy: &Galaxy,
    civ_id: u32,
    range_ly: f64,
    fuel_per_ly: f64,
    cap_cost: f64,
) -> std::collections::BTreeMap<u32, f64> {
    use std::cmp::Reverse;
    use std::collections::{BTreeMap, BinaryHeap};

    // Queue entries are (cost bits, system); Reverse makes the
    // binary heap pop the cheapest first. The system id tie-break
    // keeps traversal order deterministic.
    let mut dist: BTreeMap<u32, f64> = BTreeMap::new();
    let mut heap: BinaryHeap<Reverse<(u64, u32)>> = BinaryHeap::new();
    for colony in campaign.colonies_of(civ_id) {
        dist.insert(colony, 0.0);
        heap.push(Reverse((0, colony)));
    }
    while let Some(Reverse((cost_bits, node))) = heap.pop() {
        let cost = f64::from_bits(cost_bits);
        if dist.get(&node).map(|d| cost > *d + 1e-12).unwrap_or(false) {
            continue;
        }
        if cost >= cap_cost {
            continue;
        }
        for (hop_ly, next) in campaign.neighbors_within(galaxy, node, range_ly) {
            let next_cost = cost + hop_ly * fuel_per_ly;
            if next_cost <= cap_cost
                && next_cost + 1e-12 < *dist.get(&next).unwrap_or(&f64::INFINITY)
            {
                dist.insert(next, next_cost);
                heap.push(Reverse((next_cost.to_bits(), next)));
            }
        }
    }
    dist
}

/// Distance from `system` to this civilization's nearest colony
/// (0 when the system itself holds one).
fn nearest_own_colony_distance(
    campaign: &Campaign,
    galaxy: &Galaxy,
    civ_id: u32,
    system: u32,
) -> Option<f64> {
    campaign
        .colonies_of(civ_id)
        .into_iter()
        .filter_map(|colony| galaxy.distance_ly(system, colony))
        .min_by(|a, b| a.total_cmp(b))
}

/// Send idle ships out: colony ships to this civilization's best
/// claimed-and-unsettled systems, surveyors to its nearest
/// unsurveyed systems. All targeting uses only what the civilization
/// itself knows.
fn dispatch_idle_ships(
    campaign: &mut Campaign,
    galaxy: &Galaxy,
    civ_id: u32,
    return_costs: &std::collections::BTreeMap<u32, f64>,
) {
    // Colony targets first. Score is habitability plus a frontier
    // bonus: a new colony is also a refuel depot, and colonies at
    // the edge of known space extend the surveyors' reach far more
    // than another world next door to home (§5.2's fuel logistics
    // make depot placement the expansion bottleneck).
    let mut targets: Vec<(f64, u32)> = campaign
        .surveyed_systems_of(civ_id)
        .into_iter()
        .filter_map(|system| {
            let state = campaign.system(system)?;
            if state.claimed_by != Some(civ_id) || state.colony.is_some() {
                return None;
            }
            let profile = campaign.known_profile(civ_id, system)?;
            if profile.habitability_percent < MIN_CLAIM_HABITABILITY {
                return None;
            }
            let frontier = nearest_own_colony_distance(campaign, galaxy, civ_id, system)
                .unwrap_or(0.0);
            Some((profile.habitability_percent + 0.3 * frontier, system))
        })
        .collect();
    targets.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.cmp(&b.1)));
    let mut taken: Vec<u32> = Vec::new();

    for ship_id in campaign.ships_of(civ_id) {
        let Some(ship) = campaign.ship(ship_id) else {
            continue;
        };
        let ShipState::AtSystem { system: at } = ship.state else {
            continue;
        };
        let fuel_on_board = ship.fuel;
        let Some(design) = campaign.design(ship.design_idx).cloned() else {
            continue;
        };
        match design.kind {
            ShipKind::Colony => {
                // Best reachable target not already assigned this
                // month. Unreachable claims wait for a closer ship
                // or a forward colony rather than failing monthly.
                let target = targets
                    .iter()
                    .map(|(_, s)| *s)
                    .filter(|s| !taken.contains(s))
                    .find(|s| {
                        *s == at
                            || galaxy
                                .distance_ly(at, *s)
                                .map(|d| {
                                    d <= design.range_ly() + 1e-9
                                        && d * design.fuel_per_ly <= fuel_on_board + 1e-9
                                })
                                .unwrap_or(false)
                    });
                if let Some(target) = target {
                    let result = if target == at {
                        campaign
                            .found_colony_with_ship_for(civ_id, ship_id)
                            .map(|_| ())
                    } else {
                        campaign.dispatch_ship_for(
                            civ_id,
                            galaxy,
                            ship_id,
                            target,
                            Purpose::Colonize,
                        )
                    };
                    if result.is_ok() {
                        taken.push(target);
                    }
                }
            }
            ShipKind::Surveyor => {
                // Survey in place first if this system is unknown
                // to us (e.g. a fresh build at a frontier colony).
                if !campaign.surveyed_by(civ_id, at) {
                    let _ = campaign.begin_survey_for(civ_id, galaxy, ship_id);
                    continue;
                }
                // Prudent frontier hop (the S1 policy's rule, §5.2):
                // go only where the tanks also hold the trip back
                // to one of our colonies — costed as the shortest
                // hop-by-hop path home, not the straight line, so
                // sparse regions price their returns honestly.
                // Without it surveyors chain single legs outward
                // until they sit at a dry frontier system forever,
                // and expansion stalls a few hops from home.
                let near = campaign.neighbors_within(galaxy, at, design.range_ly());
                let target = near.iter().find(|(dist, id)| {
                    if campaign.surveyed_by(civ_id, *id) {
                        return false;
                    }
                    let outbound = *dist * design.fuel_per_ly;
                    let return_cost = return_costs.get(id).copied().unwrap_or(f64::INFINITY);
                    outbound + return_cost <= fuel_on_board + 1e-9
                });
                if let Some((_, target)) = target {
                    let _ = campaign.dispatch_ship_for(
                        civ_id,
                        galaxy,
                        ship_id,
                        *target,
                        Purpose::Survey,
                    );
                    continue;
                }
                // No prudent hop: walk home toward the nearest own
                // colony, one reachable leg at a time, unless we
                // are already at one (the refuel step tops us up
                // there and next month may open a frontier).
                let at_own_colony = campaign
                    .system(at)
                    .map(|s| s.colony.is_some() && s.claimed_by == Some(civ_id))
                    .unwrap_or(false);
                if !at_own_colony {
                    let home_leg = near
                        .iter()
                        .filter(|(dist, _)| *dist * design.fuel_per_ly <= fuel_on_board + 1e-9)
                        .min_by(|(_, a), (_, b)| {
                            let da = nearest_own_colony_distance(campaign, galaxy, civ_id, *a)
                                .unwrap_or(f64::INFINITY);
                            let db = nearest_own_colony_distance(campaign, galaxy, civ_id, *b)
                                .unwrap_or(f64::INFINITY);
                            da.total_cmp(&db)
                        });
                    if let Some((_, target)) = home_leg {
                        let _ = campaign.dispatch_ship_for(
                            civ_id,
                            galaxy,
                            ship_id,
                            *target,
                            Purpose::Relocate,
                        );
                    }
                }
            }
            // S5 warships are driven by the war step below; gate
            // builders are not part of the AI's S5 repertoire.
            _ => {}
        }
    }
}

/// S4 diplomacy (design §6.3): one month of treaty business for
/// this civilization, conducted entirely through the core's public
/// deal commands — the same stated-reasons evaluation the player
/// faces, with no AI back door. Personality drives the agenda:
/// honour decides whether treaties hold and whether embargoes are
/// beneath it, aggression whether embargoes and hard lines appeal,
/// trade affinity (inside the evaluation) what gets offered first.
///
/// Per contacted civilization, in order: embargo management
/// (lift when relations recover; declare against the hated when
/// aggressive and unbound), settlement of old disputes, treaty
/// breaking when a relation has rotted past saving, new treaty
/// proposals (one instrument per pair per month; at most one fresh
/// offer to the player per month), and trade-route opening under
/// an active trade agreement.
fn diplomacy_step(
    campaign: &mut Campaign,
    galaxy: &Galaxy,
    civ_id: u32,
    personality: Personality,
) {
    let contacted: Vec<u32> = campaign
        .civs()
        .iter()
        .map(|c| c.id)
        .filter(|&id| id != civ_id && campaign.has_contact(civ_id, id))
        .collect();
    let mut proposed_to_player = false;

    for other in contacted {
        if !campaign.diplomacy_open(civ_id, other) {
            continue;
        }
        let opinion = campaign.relation(galaxy, civ_id, other).opinion.total;

        // Embargoes: lift mine when the relation has recovered;
        // while either direction stands, no deals are weighed.
        if campaign.embargo_of(civ_id, other).is_some() {
            if opinion >= 0.0 {
                let _ = campaign.lift_embargo_for(civ_id, other);
            }
            continue;
        }
        if campaign.embargo_of(other, civ_id).is_some() {
            continue;
        }
        // Declare: only against a civ we genuinely dislike, only
        // when aggressive, and not while bound by treaties an
        // embargo would tangle (a trade agreement is the exception
        // — an embargo *is* its termination, breach and all).
        let bound = TreatyKind::ALL
            .iter()
            .any(|&k| k != TreatyKind::TradeAgreement && campaign.treaty_active(civ_id, other, k));
        if opinion <= -35.0 && personality.aggression >= 0.55 && personality.honour < 0.6 && !bound
        {
            let _ = campaign.declare_embargo_for(civ_id, other);
            continue;
        }

        // Settle disputes that have had half a year to cool: a
        // recognition settlement (no cessions, no credits) when
        // both sides' evaluations accept it.
        let disputes = campaign.disputes_between(civ_id, other);
        let oldest_days = disputes
            .iter()
            .map(|d| campaign.day().saturating_sub(d.opened_day))
            .max()
            .unwrap_or(0);
        if !disputes.is_empty() && oldest_days >= 180 {
            let terms = PeaceTerms::recognition_only();
            if campaign.evaluate_peace(galaxy, civ_id, other, &terms).accept {
                if other == PLAYER_CIV {
                    if !proposed_to_player
                        && matches!(
                            campaign.propose_peace_for(civ_id, galaxy, other, terms),
                            Ok(DealOutcome::Pending { .. })
                        )
                    {
                        proposed_to_player = true;
                    }
                } else {
                    let _ = campaign.propose_peace_for(civ_id, galaxy, other, terms);
                }
            }
        }

        // Break a treaty when the relation has rotted: faithless
        // civs walk away freely; honourable ones walk only from a
        // partner who broke faith first. The least-valued
        // instrument goes first; an alliance holds to −60.
        if opinion <= -45.0 {
            let they_breached_us = campaign
                .breaches()
                .iter()
                .any(|b| b.breaker == other && b.other == civ_id);
            if personality.honour < 0.5 || they_breached_us {
                for kind in [
                    TreatyKind::ResearchPact,
                    TreatyKind::GateAccess,
                    TreatyKind::NonAggressionPact,
                    TreatyKind::TradeAgreement,
                    TreatyKind::Alliance,
                ] {
                    if kind == TreatyKind::Alliance && opinion > -60.0 {
                        continue;
                    }
                    if campaign.treaty_active(civ_id, other, kind) {
                        let _ = campaign.break_treaty_for(civ_id, other, kind);
                        break;
                    }
                }
                continue;
            }
        }

        // New instruments, in a fixed order; the evaluation decides
        // what this civ actually wants, kind by kind.
        for kind in TreatyKind::ALL {
            if campaign.treaty_active(civ_id, other, kind) {
                continue;
            }
            if !campaign.evaluate_treaty(galaxy, civ_id, other, kind).accept {
                continue;
            }
            if other == PLAYER_CIV {
                if proposed_to_player {
                    continue;
                }
                if matches!(
                    campaign.propose_treaty_for(civ_id, galaxy, other, kind),
                    Ok(DealOutcome::Pending { .. })
                ) {
                    proposed_to_player = true;
                }
            } else {
                let _ = campaign.propose_treaty_for(civ_id, galaxy, other, kind);
            }
            break;
        }

        // Trade routes under an active agreement: keep up to two
        // running, best endpoints first (the core's one suggestion
        // rule serves AI and player alike).
        if campaign.treaty_active(civ_id, other, TreatyKind::TradeAgreement) {
            while campaign.routes_between(civ_id, other).len() < 2 {
                let Some((mine, theirs, _, _)) =
                    campaign.suggest_trade_route(galaxy, civ_id, other)
                else {
                    break;
                };
                let already = campaign
                    .routes_between(civ_id, other)
                    .iter()
                    .any(|r| {
                        (r.system_a == mine && r.system_b == theirs)
                            || (r.system_a == theirs && r.system_b == mine)
                    });
                if already {
                    break;
                }
                if campaign
                    .establish_trade_route_for(civ_id, galaxy, other, mine, theirs)
                    .is_err()
                {
                    break;
                }
            }
        }
    }
}

/// S5 war planning (§6.4), one month for one civilization:
/// exhaustion sues for peace, live wars get fleets and invasions,
/// and new wars are declared only through the stated gates. Every
/// act goes through the core's public commands; failures (range,
/// fuel, cooldowns) simply mean "not this month".
fn war_step(campaign: &mut Campaign, galaxy: &Galaxy, civ_id: u32, personality: Personality) {
    let enemies: Vec<u32> = campaign
        .wars()
        .iter()
        .filter(|w| w.parties.0 == civ_id || w.parties.1 == civ_id)
        .map(|w| {
            if w.parties.0 == civ_id {
                w.parties.1
            } else {
                w.parties.0
            }
        })
        .collect();

    // Exhaustion sues: at 35 or beyond, offer recognition terms
    // (no cessions, no credits) in every war we fight — the
    // counterparty's own evaluation decides, exactly as it does
    // for the player's offers.
    if !enemies.is_empty() && campaign.war_exhaustion(civ_id) >= 35.0 {
        for &enemy in &enemies {
            let terms = PeaceTerms::recognition_only();
            if campaign.evaluate_peace(galaxy, civ_id, enemy, &terms).accept {
                let _ = campaign.propose_peace_for(civ_id, galaxy, enemy, terms);
            }
        }
    }

    if !enemies.is_empty() {
        build_warships(campaign, civ_id, enemies.len());
        conduct_war(campaign, galaxy, civ_id, &enemies);
    }

    // Declarations. The gates, all stated: real aggression, a
    // relation already cold, a grievance (an open dispute) or
    // hatred deep enough to need none, honour's insistence on a
    // grievance, and a strength comparison made only from what we
    // can see — enemy ships at systems we have surveyed.
    if personality.aggression < 0.6 {
        return;
    }
    let my_strength = fleet_strength(campaign, civ_id, None);
    let has_warship = campaign.ships_of(civ_id).iter().any(|id| {
        campaign
            .ship(*id)
            .map(|s| {
                matches!(
                    campaign.designs()[s.design_idx as usize].kind,
                    ShipKind::Frigate | ShipKind::Cruiser
                )
            })
            .unwrap_or(false)
    });
    // Peacetime fleets are built by the war step only once a war
    // exists; a civilization with no warship declares nothing —
    // except that it may still arm first: frigate construction in
    // peacetime is how a declaration becomes possible at all, so
    // an aggressive, aggrieved civilization builds toward one.
    let contacted: Vec<u32> = campaign
        .civs()
        .iter()
        .map(|c| c.id)
        .filter(|&id| id != civ_id && campaign.diplomacy_open(civ_id, id))
        .collect();
    for other in contacted {
        if campaign.at_war(civ_id, other) {
            continue;
        }
        // A civilization with no colonies has nothing to fight
        // over — war with it is a gesture, and the war would end
        // itself at the next settlement anyway.
        if campaign.colonies_of(other).is_empty() {
            continue;
        }
        let opinion = campaign.relation(galaxy, civ_id, other).opinion.total;
        if opinion > -20.0 {
            continue;
        }
        let has_dispute = !campaign.disputes_between(civ_id, other).is_empty();
        if !has_dispute && opinion > -45.0 {
            continue;
        }
        if personality.honour >= 0.7 && !has_dispute {
            continue;
        }
        if campaign.treaty_active(civ_id, other, TreatyKind::Alliance)
            && !(opinion <= -60.0 && personality.honour < 0.4)
        {
            continue;
        }
        if !has_warship {
            // Arm toward a declaration: queue one frigate at the
            // richest idle colony, then wait for next month.
            build_warships(campaign, civ_id, 1);
            continue;
        }
        let their_visible = fleet_strength(campaign, other, Some(civ_id));
        if their_visible > my_strength / 1.2 {
            continue;
        }
        if their_visible <= 0.0 && personality.aggression < 0.75 {
            continue;
        }
        let _ = campaign.declare_war_for(civ_id, other);
    }
}

/// Visible fleet strength: the sum of attack + defence over a
/// civilization's ships. With `observer` set, only ships sitting
/// at systems the observer has surveyed count — the fog-honest
/// form used for declarations. Without, the civilization's own
/// full strength (a civ always knows its own fleet).
fn fleet_strength(campaign: &Campaign, civ_id: u32, observer: Option<u32>) -> f64 {
    campaign
        .ships_of(civ_id)
        .iter()
        .filter_map(|id| campaign.ship(*id))
        .filter(|ship| match (observer, ship.state.current_system()) {
            (Some(obs), Some(system)) => campaign.surveyed_by(obs, system),
            (Some(_), None) => false,
            (None, _) => true,
        })
        .map(|ship| {
            let d = &campaign.designs()[ship.design_idx as usize];
            d.attack + d.defence
        })
        .sum()
}

/// Build warships while at war (or arming toward a declaration):
/// frigates up to a small fleet scaled by the number of wars,
/// then a cruiser when the treasury is deep. One build per idle
/// colony per month, richest-alloy colony first as in the S3
/// builder.
fn build_warships(campaign: &mut Campaign, civ_id: u32, war_count: usize) {
    let designs = campaign.designs().to_vec();
    let frigate_idx = designs.iter().position(|d| d.kind == ShipKind::Frigate);
    let cruiser_idx = designs.iter().position(|d| d.kind == ShipKind::Cruiser);
    let (Some(frigate_idx), Some(cruiser_idx)) = (frigate_idx, cruiser_idx) else {
        return;
    };
    let frigate_target = 1 + war_count;
    for system in campaign.colonies_of(civ_id) {
        let Some(state) = campaign.system(system) else {
            continue;
        };
        let Some(colony) = &state.colony else {
            continue;
        };
        if !colony.construction_queue.is_empty() {
            continue;
        }
        let frigates = count_ships_of_kind(campaign, civ_id, &designs, ShipKind::Frigate);
        let cruisers = count_ships_of_kind(campaign, civ_id, &designs, ShipKind::Cruiser);
        let want = if frigates < frigate_target {
            Some(frigate_idx)
        } else if cruisers < war_count
            && campaign.credits_for(civ_id) >= designs[cruiser_idx].credits_cost() + 500.0
        {
            Some(cruiser_idx)
        } else {
            None
        };
        if let Some(idx) = want {
            let _ = campaign.build_ship_for(civ_id, system, idx as u32);
        }
    }
}

/// Count one civilization's ships of one design kind.
fn count_ships_of_kind(
    campaign: &Campaign,
    civ_id: u32,
    designs: &[crate::state::ShipDesign],
    kind: ShipKind,
) -> usize {
    campaign
        .ships_of(civ_id)
        .iter()
        .filter(|id| {
            campaign
                .ship(**id)
                .map(|s| designs[s.design_idx as usize].kind == kind)
                .unwrap_or(false)
        })
        .count()
}

/// Sail the fleet: every idle warship heads for the nearest enemy
/// colony its civilization has surveyed (checked orders — a ship
/// that cannot reach a target this month waits), and a warship
/// already over an enemy colony attempts the invasion the core
/// adjudicates (defending fleet gone, troops over garrison).
fn conduct_war(campaign: &mut Campaign, galaxy: &Galaxy, civ_id: u32, enemies: &[u32]) {
    // Enemy colonies we can actually see: fog of war binds the AI
    // exactly as it binds the player.
    let mut targets: Vec<u32> = Vec::new();
    for &enemy in enemies {
        for system in campaign.colonies_of(enemy) {
            if campaign.surveyed_by(civ_id, system) {
                targets.push(system);
            }
        }
    }
    if targets.is_empty() {
        return;
    }
    targets.sort_unstable();
    targets.dedup();
    for ship_id in campaign.ships_of(civ_id) {
        let Some(ship) = campaign.ship(ship_id) else {
            continue;
        };
        let ShipState::AtSystem { system: at } = ship.state else {
            continue;
        };
        let kind = campaign.designs()[ship.design_idx as usize].kind;
        if !matches!(kind, ShipKind::Frigate | ShipKind::Cruiser) {
            continue;
        }
        if targets.contains(&at) {
            let _ = campaign.invade_system_for(civ_id, at);
            continue;
        }
        let mut ordered = targets.clone();
        ordered.sort_by(|&x, &y| {
            let dx = galaxy.distance_ly(at, x).unwrap_or(f64::INFINITY);
            let dy = galaxy.distance_ly(at, y).unwrap_or(f64::INFINITY);
            dx.total_cmp(&dy).then(x.cmp(&y))
        });
        for target in ordered {
            if campaign
                .dispatch_ship_for(civ_id, galaxy, ship_id, target, Purpose::Relocate)
                .is_ok()
            {
                break;
            }
        }
    }
}
