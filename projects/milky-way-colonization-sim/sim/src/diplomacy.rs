//! Contact records, claim disputes, and the legible opinion model
//! (design §6.2/§6.3).
//!
//! Opinions are a **pure function of campaign state**: nothing here
//! is stored except first-contact days and the dispute records
//! themselves, so the numbers a player sees are always derivable
//! from the state they can inspect — no hidden opinion black box,
//! per §6.2. Components that belong to later slices (trade volume
//! S4, shared enemies and broken treaties S5) are zero in S3 and
//! simply absent from the breakdown.

use crate::catalog::Galaxy;
use crate::state::{Campaign, Dispute, StarId, DAYS_PER_MONTH, PLAYER_CIV};

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
    /// disposition + disputes + border_friction.
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

        Relation {
            contacted_day: self.contacted_day(observer, subject),
            opinion: OpinionBreakdown {
                disposition,
                disputes: dispute_penalty,
                border_friction,
                total: disposition + dispute_penalty + border_friction,
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
