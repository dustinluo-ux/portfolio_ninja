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
