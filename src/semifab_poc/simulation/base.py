"""Versioned contract for deterministic latent-state plant subsystems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, Mapping, TypeVar


StateT = TypeVar("StateT")
ConfigT = TypeVar("ConfigT")


class DynamicSubsystem(ABC, Generic[StateT, ConfigT]):
    """Stateful-config interface for a deterministic physical subsystem.

    Version 2 deliberately excludes sensing. Physical subsystems own immutable,
    validated configuration and transform immutable latent states. The separate
    ``SensorModel`` owns sampling clocks, corruption, and communication state.
    """

    interface_version = "2.0.0"
    config: ConfigT

    @abstractmethod
    def reset(self, initial_state: StateT | None = None) -> StateT:
        """Return a validated explicit or documented nominal latent state."""

    @abstractmethod
    def step(
        self,
        state: StateT,
        action: Mapping[str, Any] | None,
        disturbance: Mapping[str, Any] | None,
        dt_s: float,
    ) -> StateT:
        """Return a new invariant-valid state without mutating ``state``."""
