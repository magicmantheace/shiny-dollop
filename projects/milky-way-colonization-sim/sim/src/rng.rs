//! Deterministic seeded randomness for the simulation core.
//!
//! The core owns all randomness. A campaign seed creates the root
//! stream; system-profile generation derives an independent child
//! stream from `(campaign seed, star id)`, so revealing one system can
//! never change the generated contents of another and decision order
//! cannot leak into a system's fixed profile.

/// A small SplitMix64 generator. It is used because its state is one
/// `u64`, which makes canonical serialization and save/load trivial.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SeededRng {
    state: u64,
}

impl SeededRng {
    pub fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    pub fn state(&self) -> u64 {
        self.state
    }

    pub fn from_state(state: u64) -> Self {
        Self { state }
    }

    pub fn next_u64(&mut self) -> u64 {
        self.state = self.state.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.state;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Uniform value in `[0, 1)`, constructed from the top 53 bits.
    pub fn next_f64(&mut self) -> f64 {
        const SCALE: f64 = 1.0 / ((1u64 << 53) as f64);
        ((self.next_u64() >> 11) as f64) * SCALE
    }

    /// Integer in `[0, bound)`. `bound` must not be zero.
    pub fn next_below(&mut self, bound: u64) -> u64 {
        debug_assert!(bound > 0);
        self.next_u64() % bound
    }

    /// A deterministic child stream for one star in one campaign.
    pub fn child_for_star(seed: u64, star_id: u32) -> Self {
        let mixed = seed ^ (star_id as u64).wrapping_mul(0xD1B5_4A32_D192_ED03);
        let mut rng = Self::new(mixed);
        // Warm the stream so nearby star ids do not produce visibly
        // correlated first draws.
        for _ in 0..4 {
            rng.next_u64();
        }
        rng
    }
}

/// A stable, non-cryptographic hash used only to derive deterministic
/// durations/traits from identifiers. Canonical save integrity uses
/// SHA-256 (from the pipeline crate), not this function.
pub fn stable_hash64(mut x: u64) -> u64 {
    x ^= x >> 33;
    x = x.wrapping_mul(0xff51_afd7_ed55_8ccd);
    x ^= x >> 33;
    x = x.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    x ^ (x >> 33)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_stream() {
        let mut a = SeededRng::new(42);
        let mut b = SeededRng::new(42);
        for _ in 0..128 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
    }

    #[test]
    fn child_streams_are_star_specific_and_repeatable() {
        let mut a = SeededRng::child_for_star(7, 100);
        let mut b = SeededRng::child_for_star(7, 100);
        let mut c = SeededRng::child_for_star(7, 101);
        assert_eq!(a.next_u64(), b.next_u64());
        assert_ne!(a.next_u64(), c.next_u64());
    }
}
