from __future__ import annotations

from abc import ABC, abstractmethod

from .objects import ExecutionIntent, MarketDataset, Universe


class DataAdapter(ABC):
    @abstractmethod
    def fetch(self, universe: Universe, window_days: int) -> MarketDataset:
        ...


class ExecutionAdapter(ABC):
    @abstractmethod
    def submit(self, intent: ExecutionIntent) -> None:
        ...
