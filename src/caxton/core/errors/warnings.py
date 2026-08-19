class CaxtonWarning(Warning):
    """Base class for every warning emitted by caxton."""


class DocumentWarning(CaxtonWarning):
    """Base category retained for document-generation warnings."""


class PerformanceWarning(DocumentWarning):
    """Warn about an operation with a potentially surprising runtime cost."""


class ExperimentalFeatureWarning(DocumentWarning):
    """Warn that an API or capability is experimental."""
