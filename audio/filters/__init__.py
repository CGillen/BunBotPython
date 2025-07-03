"""
Advanced Digital Filter System

This package provides high-performance digital filter implementations
using scipy.signal for audio processing.
"""

from .design.filter_designer import ScipyFilterDesigner, FilterDesignService
from .digital_filter import DigitalFilter, FilterBank
from .exceptions import FilterDesignError, FilterProcessingError

__all__ = [
    'ScipyFilterDesigner',
    'FilterDesignService',
    'DigitalFilter',
    'FilterBank',
    'FilterDesignError',
    'FilterProcessingError'
]
