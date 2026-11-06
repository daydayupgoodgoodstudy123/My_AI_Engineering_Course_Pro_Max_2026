"""Entity memory: facts about a customer, an account or an issue, kept in a dbm file."""
from __future__ import annotations

import dbm
import json


class EntityMemory:
    """Per-entity facts that survive across kickoffs (CrewAI's entity memory).

    The store is a dbm file with one key per entity, the entity's name in UTF-8. Its value is
    every fact about that entity, as one JSON object of {fact: text}. Facts are found by the
    exact entity name, never by similarity: "Acme" and "Acme Labs" are two customers.
    """

    def __init__(self, path: str) -> None:
        """Open the store at path, creating it when needed; facts from earlier kickoffs are kept."""
        self._db = dbm.open(path, "c")

    def remember(self, entity: str, facts: dict[str, str]) -> None:
        """Record facts about entity. A fact given again replaces its old text; the entity's other
        facts are kept. An empty entity name is a ValueError.
        """
        if not entity:
            raise ValueError("an entity needs a name")
        if not facts:
            return
        known = self.recall(entity)
        known.update(facts)
        self._db[entity.encode("utf-8")] = json.dumps(known)

    def recall(self, entity: str) -> dict[str, str]:
        """Every fact about entity, exactly as remembered. An unknown entity has none: {}."""
        raw = self._db.get(entity.encode("utf-8"))
        return {} if raw is None else json.loads(raw)

    def entities(self) -> list[str]:
        """The names of every entity with facts, sorted."""
        return sorted(key.decode("utf-8") for key in self._db.keys())

    def close(self) -> None:
        self._db.close()
