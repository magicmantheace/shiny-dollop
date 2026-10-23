from __future__ import annotations

from hashlib import sha256

from .crawl_domain import Crawl, ParticipationStatus
from .crawler_social import relationship, willingness_to_help
from .gameplay_domain import CrawlParty, LootPolicy


def _stable_party_id(crawl: Crawl, members: list[str]) -> str:
    payload = f"{crawl.id}:party:{crawl.current_floor}:{crawl.current_tick}:{','.join(sorted(members))}"
    return f"party_{sha256(payload.encode()).hexdigest()[:20]}"


def compatibility(crawl: Crawl, left_id: str, right_id: str) -> float:
    left = crawl.participants[left_id]
    right = crawl.participants[right_id]
    if left.agent is None or right.agent is None:
        return 0.0
    rel = relationship(left.agent, right_id)
    reciprocal = relationship(right.agent, left_id)
    trait_fit = (
        left.agent.traits.sociability
        + right.agent.traits.sociability
        + left.agent.traits.loyalty
        + right.agent.traits.loyalty
    ) / 4.0
    trust = (max(-1.0, rel.trust) + max(-1.0, reciprocal.trust) + 2.0) / 4.0
    resentment = (rel.resentment + reciprocal.resentment) / 2.0
    return max(0.0, min(1.0, 0.45 * trait_fit + 0.45 * trust - 0.35 * resentment))


def maybe_form_party(crawl: Crawl, member_ids: list[str]) -> CrawlParty | None:
    eligible = [
        npc_id
        for npc_id in sorted(set(member_ids))
        if npc_id in crawl.participants
        and crawl.participants[npc_id].status == ParticipationStatus.ACTIVE
        and crawl.participants[npc_id].current_party_id is None
        and crawl.participants[npc_id].agent is not None
    ]
    if len(eligible) < 2:
        return None

    pairs: list[tuple[float, str, str]] = []
    for index, left in enumerate(eligible):
        for right in eligible[index + 1 :]:
            pairs.append((compatibility(crawl, left, right), left, right))
    pairs.sort(key=lambda row: (-row[0], row[1], row[2]))
    if not pairs or pairs[0][0] < 0.48:
        return None

    _, left, right = pairs[0]
    members = [left, right]
    for candidate in eligible:
        if candidate in members or len(members) >= 5:
            continue
        average = sum(compatibility(crawl, candidate, member) for member in members) / len(members)
        if average >= 0.54:
            members.append(candidate)

    leader = max(
        members,
        key=lambda npc_id: (
            crawl.participants[npc_id].agent.skills.leadership,
            crawl.participants[npc_id].agent.traits.sociability,
            npc_id,
        ),
    )
    greedy = sum(crawl.participants[npc_id].agent.traits.greed for npc_id in members) / len(members)
    empathetic = sum(crawl.participants[npc_id].agent.traits.empathy for npc_id in members) / len(members)
    if empathetic > 0.62:
        policy = LootPolicy.NEED_BEFORE_GREED
    elif greedy > 0.67:
        policy = LootPolicy.FINDERS_KEEPERS
    else:
        policy = LootPolicy.EQUAL_SHARE

    pair_total = sum(
        compatibility(crawl, left_id, right_id)
        for index, left_id in enumerate(members)
        for right_id in members[index + 1 :]
    )
    pair_count = max(1, len(members) * (len(members) - 1) // 2)
    party = CrawlParty(
        id=_stable_party_id(crawl, members),
        leader_npc_id=leader,
        member_npc_ids=sorted(members),
        loot_policy=policy,
        cohesion=round(pair_total / pair_count, 4),
        formed_tick=crawl.current_tick,
    )
    crawl.parties[party.id] = party
    for npc_id in party.member_npc_ids:
        crawl.participants[npc_id].current_party_id = party.id
    return party


def party_for(crawl: Crawl, npc_id: str) -> CrawlParty | None:
    party_id = crawl.participants[npc_id].current_party_id
    return crawl.parties.get(party_id) if party_id else None


def should_rescue(crawl: Crawl, helper_id: str, target_id: str, danger: float) -> bool:
    helper = crawl.participants[helper_id]
    if helper.agent is None:
        return False
    willingness = willingness_to_help(helper.agent, target_id)
    courage = helper.agent.traits.courage
    loyalty_bonus = 0.20 if helper.current_party_id and helper.current_party_id == crawl.participants[target_id].current_party_id else 0.0
    return willingness + courage * 0.30 + loyalty_bonus >= 0.48 + danger * 0.35


def update_party_stability(crawl: Crawl, party_id: str) -> bool:
    party = crawl.parties[party_id]
    if not party.active:
        return False

    active_members = [
        npc_id
        for npc_id in party.member_npc_ids
        if crawl.participants[npc_id].status == ParticipationStatus.ACTIVE
    ]

    # If a party no longer has enough active members to exist, dissolve it before
    # compacting its roster. Inactive parties retain their last valid historical
    # membership, which keeps the leader/member invariant intact for persistence
    # and replay while participant-side membership links are cleared below.
    if len(active_members) < 2:
        dissolve_party(crawl, party_id)
        return False

    removed = set(party.member_npc_ids) - set(active_members)
    for npc_id in removed:
        if crawl.participants[npc_id].current_party_id == party_id:
            crawl.participants[npc_id].current_party_id = None
    party.member_npc_ids = active_members

    if party.leader_npc_id not in active_members:
        party.leader_npc_id = max(
            active_members,
            key=lambda npc_id: (
                crawl.participants[npc_id].agent.skills.leadership if crawl.participants[npc_id].agent else 0.0,
                crawl.participants[npc_id].agent.traits.sociability if crawl.participants[npc_id].agent else 0.0,
                npc_id,
            ),
        )

    cohesion = sum(
        compatibility(crawl, left, right)
        for index, left in enumerate(active_members)
        for right in active_members[index + 1 :]
    ) / max(1, len(active_members) * (len(active_members) - 1) / 2)
    party.cohesion = max(0.0, min(1.0, cohesion - party.disagreement * 0.25))
    if party.cohesion < 0.24:
        dissolve_party(crawl, party_id)
        return False
    return True


def dissolve_party(crawl: Crawl, party_id: str) -> None:
    party = crawl.parties[party_id]
    party.active = False
    for npc_id in list(party.member_npc_ids):
        if crawl.participants[npc_id].current_party_id == party_id:
            crawl.participants[npc_id].current_party_id = None
