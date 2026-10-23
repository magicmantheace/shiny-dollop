from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings
from .domain import CommandEnvelope, Kingdom, WorldState


class AIUnavailable(RuntimeError):
    pass


class AIAdapter:
    """Optional OpenAI-compatible adviser.

    The adapter can translate natural language into structured commands or suggest
    kingdom strategy, but it has no persistence object and no state mutation access.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.ai_provider.lower() != "none" and bool(self.settings.ai_model)

    def _completion(self, messages: list[dict[str, str]], temperature: float = 0.1) -> str:
        if not self.enabled:
            raise AIUnavailable("AI provider is disabled")
        headers = {"Content-Type": "application/json"}
        if self.settings.ai_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ai_api_key}"
        url = self.settings.ai_base_url.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=45.0) as client:
            response = client.post(url, headers=headers, json={
                "model": self.settings.ai_model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            })
            response.raise_for_status()
            payload = response.json()
        return payload["choices"][0]["message"]["content"]

    def parse_command(self, text: str, world: WorldState, issuer: str = "ai-admin-parser") -> CommandEnvelope:
        entity_context = {
            "kingdoms": {k.id: k.name for k in world.kingdoms.values()},
            "settlements": {s.id: s.name for s in world.settlements.values()},
            "npcs": {n.id: n.name for n in list(world.npcs.values())[:100]},
            "wars": {w.id: {"attacker": w.attacker_kingdom_id, "defender": w.defender_kingdom_id, "state": w.state.value} for w in world.wars.values()},
        }
        allowed = [
            "world.pause", "world.resume", "world.set_speed", "world.advance", "world.disaster",
            "kingdom.set_priority", "kingdom.set_tax", "kingdom.declare_war", "kingdom.change_ruler", "kingdom.mobilize",
            "settlement.add_resource", "settlement.set_stability", "settlement.build", "settlement.change_kingdom",
            "npc.travel", "npc.kill", "npc.set_goal", "npc.set_occupation", "war.end",
        ]
        prompt = (
            "Translate the administrator request into exactly one LivingWorld command. "
            "Return JSON with keys type, target_id, parameters. Do not invent entity IDs. "
            f"Allowed command types: {allowed}. Current entities: {json.dumps(entity_context)}"
        )
        content = self._completion([
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ])
        data = json.loads(content)
        if data.get("type") not in allowed:
            raise ValueError("AI returned an unsupported command type")
        data["issuer"] = issuer
        return CommandEnvelope.model_validate(data)

    def advise_kingdom(self, kingdom: Kingdom, world: WorldState) -> dict[str, Any]:
        settlements = [world.settlements[s] for s in kingdom.settlement_ids if s in world.settlements]
        compact = {
            "date": world.date.model_dump(),
            "kingdom": kingdom.model_dump(mode="json", exclude={"relations": {}}),
            "settlements": [
                {
                    "id": s.id,
                    "name": s.name,
                    "population": s.population,
                    "food_security": s.food_security,
                    "stability": s.stability,
                    "wealth": s.wealth,
                    "resources": {name: {"fill": stock.quantity / max(1, stock.capacity), "price": stock.price} for name, stock in s.resources.items()},
                }
                for s in settlements
            ],
            "relations": {rid: rel.model_dump(mode="json") for rid, rel in kingdom.relations.items()},
            "active_wars": [w.model_dump(mode="json") for w in world.active_wars() if kingdom.id in {w.attacker_kingdom_id, w.defender_kingdom_id}],
        }
        content = self._completion([
            {
                "role": "system",
                "content": "You are a medieval-fantasy ruler's strategic council. Return JSON only: {summary, priorities:[{action,reason,urgency}]}. You advise; you cannot change state.",
            },
            {"role": "user", "content": json.dumps(compact)},
        ], temperature=0.3)
        return json.loads(content)
