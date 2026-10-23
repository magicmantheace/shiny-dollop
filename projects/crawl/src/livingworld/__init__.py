"""LivingWorld deterministic simulation engine for The Underreach."""

from .politics_balance import install_political_balance_model
from .political_collapse import install_political_collapse_model
from .political_collapse_recovery import install_political_crisis_recovery_fix
from .breakaway_bootstrap import install_breakaway_political_bootstrap
from .institutions import install_institution_model
from .institution_post_advance_sync import install_post_advance_institution_sync
from .institution_fiscal_balance import install_institution_fiscal_balance
from .institution_strategic_budget import install_institution_strategic_budget
from .production import install_production_model
from .production_food_balance import install_production_food_balance
from .warfare_political_reconciliation import install_warfare_political_reconciliation

# Canonical product-facing vocabulary. These aliases deliberately reuse the proven
# legacy models so persisted snapshots, deterministic hashes, and replay truth do
# not change merely because public terminology has evolved.
from .underreach_domain import (
    Descent,
    DescentStatus,
    DescenderParticipation,
    DescenderParticipationStatus,
    LedgerEvent,
    Sector,
    SectorKind,
    Stratum,
    StratumStatus,
)
from .descender_domain import (
    DescenderAgentState,
    DescenderMemory,
    DescenderNeeds,
    DescenderPreferences,
    DescenderRelationship,
    DescenderSkills,
    DescenderTraits,
    SectorKnowledge,
    build_descender_agent,
)
from .arbiter import Arbiter, arbiter_metrics, remaining_arbiter_budget
from .echoes import Echo, EchoDetector, EchoOutput, EchoPackage, EchoReelAssembler

__version__ = "0.1.0"

# Slice 1B replaces the original unbounded faction-loyalty accumulator with an
# equilibrium strategy while preserving the rest of the Slice 1 political engine.
install_political_balance_model()

# Slice 1C replaces the original secession-only fragility hook with a sustained
# collapse model that can resolve as regime overthrow, secession, or civil war.
install_political_collapse_model()

# Correct the recovery transition so POLITICAL_CRISIS_EASED fires when a sustained
# crisis falls back below the 12-month threshold.
install_political_crisis_recovery_fix()

# A breakaway realm must have a persistent founding political cast even when its
# statistical settlement population had no tracked adult NPCs at secession time.
install_breakaway_political_bootstrap()

# Slice 2 gives explicit law choices persistent institutional consequences. The
# engine still owns all authoritative mutation; this installs deterministic policy,
# compliance, taxation, enforcement, and capacity cadence around that engine.
install_institution_model()

# FinalWorldEngine runs migration/frontier systems after LivingWorldEngine's monthly
# institution cadence. Resynchronize once the complete public advance returns so
# newly founded/transferred settlements immediately receive compliance state.
install_post_advance_institution_sync()

# Normal policy spending must remain sustainable instead of consuming every tax
# dollar and eventually pinning all kingdoms at a zero treasury. Preserve a normal
# fiscal reserve while allowing deeper emergency spending during genuine crises.
install_institution_fiscal_balance()

# Legacy quarterly kingdom investments predate Slice 2 and otherwise bypass its
# reserve floor. Expose only spendable cash above the same normal/emergency reserve
# to food, infrastructure, and military strategic decisions.
install_institution_strategic_budget()

# Slice 3 replaces independent resource growth with explicit production sites,
# material input/output chains, statistical labor allocation, household consumption,
# spoilage, and physical kingdom reserves. Install last so its post-advance sync
# composes around all prior Slice 1/2 engine wrappers.
install_production_model()

# The first 100-year Slice 3 calibration proved the material ledger but exposed an
# undersized food-processing chain and a prepared-food-only strategic reserve. Scale
# mills/foodworks/butchers with population and make grain-reserve policy store grain.
install_production_food_balance()

# Long-horizon Slice 3 validation exposed a pre-existing cross-system integrity gap:
# peace can move a living ruler/office holder with a ceded settlement while the old
# kingdom still references that NPC. Reconcile both kingdoms immediately and guard
# succession against alive rulers who now belong to another realm.
install_warfare_political_reconciliation()
