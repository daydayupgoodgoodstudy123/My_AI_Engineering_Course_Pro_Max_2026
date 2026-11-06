"""The shopping app agents are evaluated against: a pinned, self-hosted target."""
from __future__ import annotations

from typing import Any


def _whole(value: Any, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


class ShoppingApp:
    """One running copy of the shopping app.

    snapshot is the pinned state the app starts from:
        {"catalog": [{"sku": str, "name": str, "price": int}, ...],
         "cart": {sku: qty},
         "orders": [{"oid": str, "items": {sku: qty}, "total": int}, ...]}
    Prices and totals are integer cents. The catalog order is the order list_items shows.

    reset() puts the app back to exactly the pinned state. Nothing an episode does may
    change the snapshot the app was built from.
    """

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self._pinned = snapshot
        self.reset()

    def reset(self) -> None:
        pinned = self._pinned
        self.items = {row["sku"]: dict(row) for row in pinned["catalog"]}
        self.cart: dict[str, int] = dict(pinned["cart"])
        self.orders = [
            {"oid": o["oid"], "items": dict(o["items"]), "total": o["total"]}
            for o in pinned["orders"]
        ]

    @property
    def pinned_orders(self) -> int:
        """How many orders the pinned snapshot already holds."""
        return len(self._pinned["orders"])

    def state(self) -> dict[str, Any]:
        """The current state in the snapshot layout. The result is a copy."""
        return {
            "catalog": [dict(row) for row in self.items.values()],
            "cart": dict(self.cart),
            "orders": [
                {"oid": o["oid"], "items": dict(o["items"]), "total": o["total"]}
                for o in self.orders
            ],
        }

    # The actions an agent can take. An error comes back as a string starting with
    # "error:", the way the app's pages show it, and leaves the state unchanged.

    def list_items(self) -> list[dict[str, Any]]:
        """Every catalog row, in catalog order. The rows are copies."""
        return [dict(row) for row in self.items.values()]

    def add_to_cart(self, sku: str, qty: int = 1) -> str:
        """Add qty units of sku to the cart. qty must be a positive integer."""
        if sku not in {row["sku"] for row in self.list_items()}:
            return "error: unknown sku"
        self.cart[sku] = self.cart.get(sku, 0) + qty
        return f"added {qty} x {sku}"

    def remove_from_cart(self, sku: str) -> str:
        """Take sku out of the cart entirely."""
        if sku not in self.cart:
            return "error: not in cart"
        del self.cart[sku]
        return f"removed {sku}"

    def set_price(self, sku: str, price: int) -> str:
        """Change a catalog price (the store's admin side). price is integer cents, 0 or more."""
        if sku not in self.items:
            return "error: unknown sku"
        if not _whole(price, 0):
            return "error: price must be integer cents"
        self.items[sku]["price"] = price
        return f"price of {sku} is {price}"

    def checkout(self) -> str:
        """Turn the cart into an order at today's prices and return the new order id."""
        if not self.cart:
            return "error: empty cart"
        total = sum(self.items[sku]["price"] * qty for sku, qty in self.cart.items())
        oid = f"ord-{len(self.orders) + 1:03d}"
        self.orders.append({"oid": oid, "items": dict(self.cart), "total": total})
        self.cart = {}
        return oid
