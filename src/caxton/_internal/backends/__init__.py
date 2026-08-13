"""Expose bundled renderer adapters through the internal resolver seam."""

from .xlsxwriter import XlsxWriterRenderer

__all__ = ("XlsxWriterRenderer",)
