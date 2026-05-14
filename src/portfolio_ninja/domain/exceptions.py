class DataUnavailableError(Exception):
    pass


class InsufficientDataError(Exception):
    pass


class UnknownModelError(Exception):
    pass


class WeightSumError(Exception):
    pass


class ExecutionError(Exception):
    pass


class AuditIncompleteError(Exception):
    pass


class DataIntegrityError(Exception):
    pass


class IncompleteDataError(Exception):
    """Raised when a CRITICAL data source is missing or fails."""

    def __init__(self, missing_sources: list[str], criticality: str) -> None:
        self.missing_sources = list(missing_sources)
        self.criticality = str(criticality)
        super().__init__(
            f"missing_sources={self.missing_sources!r} criticality={self.criticality!r}"
        )
