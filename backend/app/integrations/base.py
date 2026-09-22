"""Shared plumbing for integration adapters."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import settings


class NotConfigured(RuntimeError):
    """Raised by any adapter that is still a placeholder or lacks credentials.
    Routes turn this into a clear 501 instead of a silent failure."""


@dataclass
class Integration:
    key: str
    name: str
    purpose: str
    inferred_from: str
    settings_keys: tuple[str, ...] = field(default_factory=tuple)
    implemented: bool = False   # True once real code replaces the placeholder

    def configured(self) -> bool:
        return all(getattr(settings, k, "") for k in self.settings_keys)

    def state(self) -> str:
        if self.implemented and self.configured():
            return "live"
        if self.configured():
            return "credentials set, adapter still a placeholder"
        return "placeholder"

    def require(self) -> None:
        if not (self.implemented and self.configured()):
            raise NotConfigured(
                f"{self.name} is not connected yet ({self.state()}). "
                f"Set {', '.join(k.upper() for k in self.settings_keys) or 'n/a'} "
                f"and implement app/integrations/{self.key.split('.')[0]}.py."
            )


registry: dict[str, Integration] = {}


def register(integration: Integration) -> Integration:
    registry[integration.key] = integration
    return integration


def status_report() -> list[dict]:
    return [
        {"key": i.key, "name": i.name, "state": i.state(), "purpose": i.purpose,
         "inferred_from": i.inferred_from}
        for i in registry.values()
    ]
