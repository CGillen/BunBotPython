"""
Filter-specific exceptions for advanced audio processing.
"""

class FilterDesignError(Exception):
    """Raised when filter design fails"""
    pass

class FilterProcessingError(Exception):
    """Raised when filter processing fails"""
    pass

class InvalidFilterSpecificationError(FilterDesignError):
    """Raised when filter specification is invalid"""
    pass

class FilterInstabilityError(FilterDesignError):
    """Raised when designed filter is unstable"""
    pass

class FilterConvergenceError(FilterDesignError):
    """Raised when filter design algorithm fails to converge"""
    pass

class UnsupportedFilterTypeError(FilterDesignError):
    """Raised when requested filter type is not supported"""
    pass
