"""Entity memory: facts about a customer, an account or an issue, kept in a dbm file."""
from __future__ import annotations


class EntityMemory:
    """Per-entity facts that survive across kickoffs (CrewAI's entity memory).

    The store is a dbm file with one key per entity, the entity's name in UTF-8. Its value is
    every fact about that entity, as one JSON object of {fact: text}. Facts are found by the
    exact entity name, never by similarity: "Acme" and "Acme Labs" are two customers.
    """

    def __init__(self, path: str) -> None:
        """Open the store at path, creating it when needed; facts from earlier kickoffs are kept."""
        raise NotImplementedError

    def remember(self, entity: str, facts: dict[str, str]) -> None:
        """Record facts about entity. A fact given again replaces its old text; the entity's other
        facts are kept. An empty entity name is a ValueError.
        """
        raise NotImplementedError

    def recall(self, entity: str) -> dict[str, str]:
        """Every fact about entity, exactly as remembered. An unknown entity has none: {}."""
        raise NotImplementedError

    def entities(self) -> list[str]:
        """The names of every entity with facts, sorted."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
