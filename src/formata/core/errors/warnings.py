class FormataWarning(Warning):
    """Base class for every warning emitted by formata."""


class DocumentWarning(FormataWarning):
    """Base category retained for document-generation warnings."""


class PerformanceWarning(DocumentWarning):
    """Warn about an operation with a potentially surprising runtime cost."""


class ExperimentalFeatureWarning(DocumentWarning):
    """Warn that an API or capability is experimental."""
