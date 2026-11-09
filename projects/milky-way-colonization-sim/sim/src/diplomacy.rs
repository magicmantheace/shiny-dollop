//! Contact records, claim disputes, and the legible opinion model
//! (design §6.2/§6.3).
//!
//! Opinions are a **pure function of campaign state**: nothing here
//! is stored except first-contact days and the dispute records
//! themselves, so the numbers a player sees are always derivable
//! from the state they can inspect — no hidden opinion black box,
//! per §6.2. S4 lights up the two components S3 left dark: trade
//! volume (from the live route ledgers) and broken treaties (from
//! the breach records). Shared enemies remain zero until war
//! exists (S5).
//!
//! S4 also hosts deal evaluation: whether an AI civilization
//! accepts a treaty or a peace settlement is computed here, as a
//! pure function returning **stated reasons** — every component a
//! named, inspectable number, so a refusal can be read, not just
//! received.

use crate::catalog::Galaxy;
use crate::state::{
    Campaign, Dispute, PeaceTerms, StarId, TreatyKind, DAYS_PER_MONTH, PLAYER_CIV,
};

/// How one civilization's opinion of another is composed. Every
/// component is a named, inspectable number (§6.2).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct OpinionBreakdown {
    /// The observer's own disposition toward everyone: trade
    /// affinity warms it, xenophobia cools it. The player has no
    /// personality vector, so the player's disposition is 0.
    pub disposition: f64,
    /// Penalty from open claim disputes between the pair.
    pub disputes: f64,
    /// Penalty from colonies of the two civilizations sitting close
    /// together — borders that touch generate friction.
    pub border_friction: f64,
    /// S4: warmth from trade actually flowing between the pair —
    /// the smaller side's cumulative earnings on their shared
    /// routes, scaled and capped (§6.2's "trade volume").
    pub trade_volume: f64,
    /// S4: penalty from the subject's remembered treaty breaches —
    /// breaches against the observer weigh most; breaches against
    /// anyone stain a reputation (§6.2's "broken treaties").
    pub broken_treaties: f64,
    /// disposition + disputes + border_friction + trade_volume
    /// + broken_treaties.
    pub total: f64,
}

/// The full relation of `observer` toward `subject`.
#[derive(Debug, Clone, PartialEq)]
pub struct Relation {
    /// Day of first contact, when the two have met.
    pub contacted_day: Option<u64>,
    pub opinion: OpinionBreakdown,
    /// Open disputes between the pair, in the order they opened.
    pub disputes: Vec<Dispute>,
}

/// Two colonies closer than this (in ly) count as a touching border.
pub const BORDER_FRICTION_RADIUS_LY: f64 = 150.0;
const BORDER_FRICTION_PER_PAIR: f64 = -2.0;
const BORDER_FRICTION_CAP: f64 = -24.0;

impl Campaign {
    /// The day two civilizations first made contact, if they have.
    pub fn contacted_day(&self, a: u32, b: u32) -> Option<u64> {
        if a == b {
            return Some(0);
        }
        let key = if a < b { (a, b) } else { (b, a) };
        self.contacts.get(&key).copied()
    }

    pub fn has_contact(&self, a: u32, b: u32) -> bool {
        self.contacted_day(a, b).is_some()
    }

    /// All open disputes involving either role for this pair.
    pub fn disputes_between(&self, a: u32, b: u32) -> Vec<Dispute> {
        self.disputes
            .iter()
            .filter(|d| {
                (d.holder == a && d.challenger == b) || (d.holder == b && d.challenger == a)
            })
            .cloned()
            .collect()
    }

    /// A dispute's visible tension (§6.3's tension meter): grows
    /// with age and with the challenger's aggression, capped so the
    /// meter has a top.
    pub fn dispute_tension(&self, dispute: &Dispute) -> f64 {
        let months_open = (self.day.saturating_sub(dispute.opened_day) / DAYS_PER_MONTH) as f64;
        let aggression = self
            .civ(dispute.challenger)
            .and_then(|c| c.personality)
            .map(|p| p.aggression)
            .unwrap_or(0.5);
        (8.0 + months_open * (0.4 + 0.6 * aggression)).min(50.0)
    }

    /// Compute `observer`'s opinion of `subject` from current state.
    pub fn relation(&self, galaxy: &Galaxy, observer: u32, subject: u32) -> Relation {
        let disposition = self
            .civ(observer)
            .and_then(|c| c.personality)
            .map(|p| p.trade_affinity * 12.0 - p.xenophobia * 24.0)
            .unwrap_or(0.0);

        let pair_disputes = self.disputes_between(observer, subject);
        let mut dispute_penalty = 0.0;
        for dispute in &pair_disputes {
            let months_open =
                (self.day.saturating_sub(dispute.opened_day) / DAYS_PER_MONTH) as f64;
            let age_term = (months_open * 0.5).min(25.0);
            // Being contested stings more than contesting.
            dispute_penalty -= if dispute.challenger == observer {
                10.0 + age_term
            } else {
                14.0 + age_term
            };
        }

        let border_friction = self.border_friction(galaxy, observer, subject);

        // S4 (§6.2): trade that has actually flowed between the
        // pair warms the relation. The smaller side's earnings are
        // the honest volume — a route only counts for as much as
        // both sides received.
        let mut shared_volume = 0.0;
        for route in self.routes_between(observer, subject) {
            shared_volume += route.earned_a.min(route.earned_b);
        }
        let trade_volume = (shared_volume * 0.04).min(20.0);

        // S4 (§6.2): faithlessness is remembered. A breach against
        // the observer costs the most; breaches against third
        // parties are reputation, at a discount.
        let mut broken_treaties: f64 = 0.0;
        for breach in &self.breaches {
            if breach.breaker == subject {
                broken_treaties -= if breach.other == observer {
                    14.0
                } else {
                    5.0
                };
            }
        }
        let broken_treaties = broken_treaties.max(-40.0);

        Relation {
            contacted_day: self.contacted_day(observer, subject),
            opinion: OpinionBreakdown {
                disposition,
                disputes: dispute_penalty,
                border_friction,
                trade_volume,
                broken_treaties,
                total: disposition + dispute_penalty + border_friction + trade_volume
                    + broken_treaties,
            },
            disputes: pair_disputes,
        }
    }

    fn border_friction(&self, galaxy: &Galaxy, a: u32, b: u32) -> f64 {
        if a == b {
            return 0.0;
        }
        let colonies_a = self.colonies_of(a);
        let colonies_b = self.colonies_of(b);
        let mut close_pairs = 0usize;
        for &x in &colonies_a {
            for &y in &colonies_b {
                if let Some(d) = galaxy.distance_ly(x, y) {
                    if d <= BORDER_FRICTION_RADIUS_LY {
                        close_pairs += 1;
                    }
                }
            }
        }
        (close_pairs as f64 * BORDER_FRICTION_PER_PAIR).max(BORDER_FRICTION_CAP)
    }

    /// The home system a civilization would name as its capital —
    /// exposed for views once contact exists.
    pub fn capital_of(&self, civ: u32) -> Option<StarId> {
        self.civ(civ).map(|c| c.home_system)
    }

    /// How many of `subject`'s colonies sit in systems `observer`
    /// has surveyed — what the observer can actually verify about
    /// the subject's size (the diplomacy screen's honest count).
    pub fn known_colonies_of(&self, observer: u32, subject: u32) -> usize {
        self.colonies_of(subject)
            .into_iter()
            .filter(|&system| self.surveyed_by(observer, system))
            .count()
    }
}

/// Re-exported so view code can name the player constant from one
/// place.
pub const PLAYER: u32 = PLAYER_CIV;

// ------------------------------------------------------------ S4 deals

/// An AI civilization's answer to a proposed deal, with its
/// workings shown (design §6.2: agendas are legible — the answer
/// states *why*, in numbers the player can inspect).
#[derive(Debug, Clone, PartialEq)]
pub struct DealEvaluation {
    pub accept: bool,
    /// The summed score the components produced.
    pub score: f64,
    /// The score the instrument required.
    pub threshold: f64,
    /// One line per component, in the order they were weighed,
    /// ending with the verdict line.
    pub reasons: Vec<String>,
}

fn signed(value: f64) -> String {
    format!("{value:+.1}")
}

impl Campaign {
    fn breaches_by(&self, breaker: u32) -> usize {
        self.breaches.iter().filter(|b| b.breaker == breaker).count()
    }

    /// Would `evaluator` accept a treaty of `kind` with
    /// `proposer`? A pure function of state: opinion, personality,
    /// and concrete interests (route potential, port value,
    /// research output, shared rivals, remembered breaches), each
    /// cited in the reasons.
    pub fn evaluate_treaty(
        &self,
        galaxy: &Galaxy,
        evaluator: u32,
        proposer: u32,
        kind: TreatyKind,
    ) -> DealEvaluation {
        if self.embargo_between(evaluator, proposer) {
            return DealEvaluation {
                accept: false,
                score: 0.0,
                threshold: 0.0,
                reasons: vec![
                    "an embargo is in force between our civilizations — no deals are \
                     weighed while trade is at war"
                        .to_string(),
                ],
            };
        }
        if kind == TreatyKind::Alliance
            && !self.disputes_between(evaluator, proposer).is_empty()
        {
            return DealEvaluation {
                accept: false,
                score: 0.0,
                threshold: 0.0,
                reasons: vec![
                    "open claim disputes between us must be settled before an alliance \
                     can be weighed"
                        .to_string(),
                ],
            };
        }
        let personality = self
            .civ(evaluator)
            .and_then(|c| c.personality)
            .unwrap_or_default();
        let opinion = self.relation(galaxy, evaluator, proposer).opinion.total;
        let breaches = self.breaches_by(proposer) as f64;
        let mut reasons: Vec<String> = Vec::new();

        let (score, threshold) = match kind {
            TreatyKind::TradeAgreement => {
                let opinion_part = opinion * 0.5;
                let affinity_part = personality.trade_affinity * 40.0;
                let (potential_part, potential_note) =
                    match self.suggest_trade_route(galaxy, evaluator, proposer) {
                        Some((sa, sb, _, _)) => {
                            let throughput = self.route_throughput(evaluator, proposer, sa, sb);
                            (
                                (throughput * 0.5).min(30.0),
                                format!(
                                    "the best route between our colonies would carry \
                                     {throughput:.1} throughput"
                                ),
                            )
                        }
                        None => (
                            0.0,
                            "no route path connects our colony networks yet".to_string(),
                        ),
                    };
                let xeno_part = -personality.xenophobia * 25.0;
                let breach_part = -breaches * 12.0;
                reasons.push(format!("our opinion of you: {}", signed(opinion)));
                reasons.push(format!(
                    "our trade affinity ({:.2}) draws us toward open markets: {}",
                    personality.trade_affinity,
                    signed(affinity_part)
                ));
                reasons.push(format!("{potential_note}: {}", signed(potential_part)));
                if personality.xenophobia > 0.0 {
                    reasons.push(format!(
                        "our xenophobia ({:.2}) makes us wary of foreign ties: {}",
                        personality.xenophobia,
                        signed(xeno_part)
                    ));
                }
                if breaches > 0.0 {
                    reasons.push(format!(
                        "you have broken {breaches:.0} treaties on record: {}",
                        signed(breach_part)
                    ));
                }
                (
                    opinion_part + affinity_part + potential_part + xeno_part + breach_part,
                    25.0,
                )
            }
            TreatyKind::GateAccess => {
                let opinion_part = opinion * 0.5;
                let affinity_part = personality.trade_affinity * 15.0;
                let ports = self.colonies_of(proposer).len() as f64;
                let ports_part = (ports * 4.0).min(24.0);
                let xeno_part = -personality.xenophobia * 20.0;
                let breach_part = -breaches * 12.0;
                reasons.push(format!("our opinion of you: {}", signed(opinion)));
                reasons.push(format!(
                    "your {ports:.0} colonies would open as ports to our ships: {}",
                    signed(ports_part)
                ));
                reasons.push(format!(
                    "our trade affinity ({:.2}) values the traffic: {}",
                    personality.trade_affinity,
                    signed(affinity_part)
                ));
                if personality.xenophobia > 0.0 {
                    reasons.push(format!(
                        "our xenophobia ({:.2}) resists foreign ships in our ports: {}",
                        personality.xenophobia,
                        signed(xeno_part)
                    ));
                }
                if breaches > 0.0 {
                    reasons.push(format!(
                        "you have broken {breaches:.0} treaties on record: {}",
                        signed(breach_part)
                    ));
                }
                (
                    opinion_part + affinity_part + ports_part + xeno_part + breach_part,
                    18.0,
                )
            }
            TreatyKind::NonAggressionPact => {
                let opinion_part = opinion * 0.4;
                let honour_part = personality.honour * 30.0;
                let aggression_part = -personality.aggression * 15.0;
                let dispute_part =
                    if self.disputes_between(evaluator, proposer).is_empty() {
                        0.0
                    } else {
                        8.0
                    };
                let breach_part = -breaches * 10.0;
                reasons.push(format!("our opinion of you: {}", signed(opinion)));
                reasons.push(format!(
                    "our honour ({:.2}) favours sworn restraint: {}",
                    personality.honour,
                    signed(honour_part)
                ));
                if personality.aggression > 0.0 {
                    reasons.push(format!(
                        "our aggression ({:.2}) chafes at restraint: {}",
                        personality.aggression,
                        signed(aggression_part)
                    ));
                }
                if dispute_part != 0.0 {
                    reasons.push(format!(
                        "open disputes between us make a pact worth having: {}",
                        signed(dispute_part)
                    ));
                }
                if breaches > 0.0 {
                    reasons.push(format!(
                        "you have broken {breaches:.0} treaties on record: {}",
                        signed(breach_part)
                    ));
                }
                (
                    opinion_part + honour_part + aggression_part + dispute_part + breach_part,
                    20.0,
                )
            }
            TreatyKind::Alliance => {
                let opinion_part = opinion * 0.8;
                let honour_part = personality.honour * 20.0;
                // Shared rivals: third parties both sides dispute
                // with — the S4 shadow of §6.2's shared enemies,
                // there being no wars yet to share.
                let mut shared = 0usize;
                for civ in self.civs() {
                    if civ.id == evaluator || civ.id == proposer {
                        continue;
                    }
                    if !self.disputes_between(evaluator, civ.id).is_empty()
                        && !self.disputes_between(proposer, civ.id).is_empty()
                    {
                        shared += 1;
                    }
                }
                let shared_part = (shared as f64 * 12.0).min(24.0);
                let xeno_part = -personality.xenophobia * 30.0;
                let breach_part = -breaches * 15.0;
                reasons.push(format!("our opinion of you: {}", signed(opinion)));
                reasons.push(format!(
                    "our honour ({:.2}) holds alliances sacred: {}",
                    personality.honour,
                    signed(honour_part)
                ));
                if shared > 0 {
                    reasons.push(format!(
                        "we dispute claims with {shared} of the same rivals: {}",
                        signed(shared_part)
                    ));
                }
                if personality.xenophobia > 0.0 {
                    reasons.push(format!(
                        "our xenophobia ({:.2}) recoils from binding ties: {}",
                        personality.xenophobia,
                        signed(xeno_part)
                    ));
                }
                if breaches > 0.0 {
                    reasons.push(format!(
                        "you have broken {breaches:.0} treaties on record: {}",
                        signed(breach_part)
                    ));
                }
                (
                    opinion_part + honour_part + shared_part + xeno_part + breach_part,
                    35.0,
                )
            }
            TreatyKind::ResearchPact => {
                let opinion_part = opinion * 0.4;
                let openness_part = (1.0 - personality.xenophobia) * 18.0;
                let partner_output = self.research_output_for(proposer);
                let research_part = (partner_output * 1.5).min(25.0);
                let affinity_part = personality.trade_affinity * 5.0;
                let breach_part = -breaches * 10.0;
                reasons.push(format!("our opinion of you: {}", signed(opinion)));
                reasons.push(format!(
                    "your research output ({partner_output:.1} points/month) would feed \
                     the pact's bonus: {}",
                    signed(research_part)
                ));
                reasons.push(format!(
                    "our openness to foreign ideas ({:.2}): {}",
                    1.0 - personality.xenophobia,
                    signed(openness_part)
                ));
                if breaches > 0.0 {
                    reasons.push(format!(
                        "you have broken {breaches:.0} treaties on record: {}",
                        signed(breach_part)
                    ));
                }
                (
                    opinion_part + openness_part + research_part + affinity_part + breach_part,
                    20.0,
                )
            }
        };

        let accept = score >= threshold;
        reasons.push(format!(
            "total {} against the {} a {} requires — {}",
            signed(score),
            signed(threshold),
            kind.label(),
            if accept { "accepted" } else { "refused" }
        ));
        DealEvaluation {
            accept,
            score,
            threshold,
            reasons,
        }
    }

    /// What a system is worth in a settlement: a colony at its
    /// development and population; a bare claim at the price of
    /// making one, roughly.
    pub fn system_value(&self, system: StarId) -> f64 {
        match self.systems.get(&system) {
            Some(state) => match &state.colony {
                Some(colony) => {
                    250.0 + colony.development as f64 * 60.0 + colony.population_millions * 0.25
                }
                None => {
                    if state.claimed_by.is_some() {
                        40.0
                    } else {
                        0.0
                    }
                }
            },
            None => 0.0,
        }
    }

    /// Would `evaluator` accept a peace settlement from `proposer`
    /// on `terms`? Weighed: the relief of closing every open
    /// dispute, the net value of the cessions and credits changing
    /// hands, and the evaluator's own disposition toward settling.
    pub fn evaluate_peace(
        &self,
        galaxy: &Galaxy,
        evaluator: u32,
        proposer: u32,
        terms: &PeaceTerms,
    ) -> DealEvaluation {
        let disputes = self.disputes_between(evaluator, proposer);
        if disputes.is_empty() && terms.is_empty() {
            return DealEvaluation {
                accept: false,
                score: 0.0,
                threshold: 0.0,
                reasons: vec!["there is nothing to settle — no open disputes, no terms offered".to_string()],
            };
        }
        let personality = self
            .civ(evaluator)
            .and_then(|c| c.personality)
            .unwrap_or_default();
        let opinion = self.relation(galaxy, evaluator, proposer).opinion.total;
        let mut reasons: Vec<String> = Vec::new();

        let tension: f64 = disputes.iter().map(|d| self.dispute_tension(d)).sum();
        let relief_part = tension * 0.8;
        if !disputes.is_empty() {
            reasons.push(format!(
                "settling {} open dispute(s) ends tension of {:.1}: {}",
                disputes.len(),
                tension,
                signed(relief_part)
            ));
        }

        // Cessions from the evaluator's chair: `cede_to_other`
        // systems come TO the evaluator when the evaluator is the
        // other party; when the evaluator is the proposer (the
        // AI-to-player offer path), the directions swap.
        let (received, given) = if evaluator == proposer {
            (&terms.cede_to_proposer, &terms.cede_to_other)
        } else {
            (&terms.cede_to_other, &terms.cede_to_proposer)
        };
        let received_value: f64 = received.iter().map(|&s| self.system_value(s)).sum();
        let given_value: f64 = given.iter().map(|&s| self.system_value(s)).sum();
        for &system in received.iter() {
            let name = galaxy
                .star(system)
                .map(|s| s.name.clone())
                .unwrap_or_else(|| format!("system {system}"));
            reasons.push(format!(
                "we receive {name} (worth {:.0})",
                self.system_value(system)
            ));
        }
        for &system in given.iter() {
            let name = galaxy
                .star(system)
                .map(|s| s.name.clone())
                .unwrap_or_else(|| format!("system {system}"));
            reasons.push(format!(
                "we cede {name} (worth {:.0})",
                self.system_value(system)
            ));
        }
        let cession_part = (received_value - given_value) * 0.06;
        if !received.is_empty() || !given.is_empty() {
            reasons.push(format!(
                "net cession value to us: {}",
                signed(cession_part)
            ));
        }
        // Credits: positive `credits_from_proposer` flows proposer
        // → other; the evaluator's gain is that flow when they are
        // the other party, and its negation when they proposed.
        let credits_gain = if evaluator == proposer {
            -terms.credits_from_proposer
        } else {
            terms.credits_from_proposer
        };
        let credits_part = credits_gain * 0.02;
        if credits_gain != 0.0 {
            reasons.push(format!(
                "credits to us: {:.0}: {}",
                credits_gain,
                signed(credits_part)
            ));
        }
        let honour_part = personality.honour * 10.0;
        let aggression_part = -personality.aggression * 10.0;
        let opinion_part = opinion * 0.3;
        reasons.push(format!("our opinion of you: {}", signed(opinion)));
        reasons.push(format!(
            "our honour ({:.2}) favours settled borders: {}",
            personality.honour,
            signed(honour_part)
        ));
        if personality.aggression > 0.0 {
            reasons.push(format!(
                "our aggression ({:.2}) prefers pressing our claims: {}",
                personality.aggression,
                signed(aggression_part)
            ));
        }

        let score = relief_part + cession_part + credits_part + honour_part + aggression_part
            + opinion_part;
        let threshold = 10.0;
        let accept = score >= threshold;
        reasons.push(format!(
            "total {} against the {} a settlement requires — {}",
            signed(score),
            signed(threshold),
            if accept { "accepted" } else { "refused" }
        ));
        DealEvaluation {
            accept,
            score,
            threshold,
            reasons,
        }
    }
}
