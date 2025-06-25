"""
Professional filter design implementation using scipy.signal.

This module provides expert-level digital filter design capabilities
with comprehensive validation, optimization, and caching.
"""

import logging
import hashlib
from typing import Dict, Optional, Tuple
import numpy as np
from scipy import signal
from scipy.signal import butter, cheby1, cheby2, ellip, bessel, firwin, firwin2

from audio.interfaces.advanced_interfaces import (
    IFilterDesigner, FilterSpecification, 
    FilterCoefficients, FilterType, FilterResponse
)
from ..exceptions import (
    FilterDesignError, InvalidFilterSpecificationError, 
    FilterInstabilityError, UnsupportedFilterTypeError
)

logger = logging.getLogger('audio.filters.design.filter_designer')

class ScipyFilterDesigner:
    """
    Expert-level filter designer using scipy.signal.
    
    Implements professional filter design algorithms with comprehensive
    validation, stability checking, and optimization.
    """
    
    def __init__(self):
        """Initialize filter designer with strategy mapping"""
        self._design_strategies = {
            FilterType.BUTTERWORTH: self._design_butterworth,
            FilterType.CHEBYSHEV_I: self._design_chebyshev1,
            FilterType.CHEBYSHEV_II: self._design_chebyshev2,
            FilterType.ELLIPTIC: self._design_elliptic,
            FilterType.BESSEL: self._design_bessel,
            FilterType.FIR: self._design_fir,
        }
        
        # Filter design limits for stability
        self._max_order = 20
        self._min_order = 1
        self._stability_margin = 0.95  # Poles must be within this radius
        
        logger.info("ScipyFilterDesigner initialized")
    
    def design_filter(self, spec: FilterSpecification) -> FilterCoefficients:
        """
        Design filter using appropriate strategy with comprehensive validation.
        
        Args:
            spec: Filter specification parameters
            
        Returns:
            Designed filter coefficients
            
        Raises:
            InvalidFilterSpecificationError: If specification is invalid
            UnsupportedFilterTypeError: If filter type not supported
            FilterDesignError: If design fails
            FilterInstabilityError: If designed filter is unstable
        """
        try:
            # Validate specification
            if not self.validate_specification(spec):
                raise InvalidFilterSpecificationError(f"Invalid filter specification: {spec}")
            
            # Get design strategy
            design_func = self._design_strategies.get(spec.filter_type)
            if not design_func:
                raise UnsupportedFilterTypeError(f"Filter type {spec.filter_type} not implemented")
            
            # Design filter
            logger.debug(f"Designing {spec.filter_type.value} {spec.response_type.value} filter, "
                        f"order={spec.order}, fc={spec.cutoff_frequencies}")
            
            coefficients = design_func(spec)
            
            # Validate stability for IIR filters
            if spec.filter_type != FilterType.FIR:
                self._validate_stability(coefficients)
            
            logger.info(f"Successfully designed {spec.filter_type.value} filter")
            return coefficients
            
        except (InvalidFilterSpecificationError, UnsupportedFilterTypeError, FilterInstabilityError):
            raise
        except Exception as e:
            logger.error(f"Filter design failed: {e}")
            raise FilterDesignError(f"Failed to design filter: {e}") from e
    
    def validate_specification(self, spec: FilterSpecification) -> bool:
        """
        Comprehensive validation of filter specification.
        
        Args:
            spec: Filter specification to validate
            
        Returns:
            True if specification is valid
        """
        try:
            # Basic parameter validation
            if spec.sample_rate <= 0:
                logger.error("Sample rate must be positive")
                return False
            
            if not (self._min_order <= spec.order <= self._max_order):
                logger.error(f"Filter order must be between {self._min_order} and {self._max_order}")
                return False
            
            # Frequency validation
            nyquist = spec.sample_rate / 2
            for freq in spec.cutoff_frequencies:
                if freq <= 0 or freq >= nyquist:
                    logger.error(f"Cutoff frequency {freq} must be between 0 and {nyquist} Hz")
                    return False
            
            # Response type specific validation
            if spec.response_type in (FilterResponse.BANDPASS, FilterResponse.BANDSTOP):
                if len(spec.cutoff_frequencies) != 2:
                    logger.error("Bandpass/bandstop filters require exactly 2 cutoff frequencies")
                    return False
                if spec.cutoff_frequencies[0] >= spec.cutoff_frequencies[1]:
                    logger.error("Lower cutoff must be less than upper cutoff")
                    return False
            else:
                if len(spec.cutoff_frequencies) != 1:
                    logger.error("Lowpass/highpass filters require exactly 1 cutoff frequency")
                    return False
            
            # Filter type specific validation
            if spec.filter_type in (FilterType.CHEBYSHEV_I, FilterType.ELLIPTIC):
                if spec.ripple_db <= 0 or spec.ripple_db > 10:
                    logger.error("Passband ripple must be between 0 and 10 dB")
                    return False
            
            if spec.filter_type in (FilterType.CHEBYSHEV_II, FilterType.ELLIPTIC):
                if spec.attenuation_db <= 0 or spec.attenuation_db > 120:
                    logger.error("Stopband attenuation must be between 0 and 120 dB")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def estimate_filter_order(self, spec: FilterSpecification) -> int:
        """
        Estimate minimum filter order for given specifications.
        
        Args:
            spec: Filter specification
            
        Returns:
            Estimated minimum filter order
        """
        try:
            nyquist = spec.sample_rate / 2
            normalized_cutoff = np.array(spec.cutoff_frequencies) / nyquist
            
            if spec.filter_type == FilterType.BUTTERWORTH:
                # Use buttord for order estimation
                if spec.response_type in (FilterResponse.BANDPASS, FilterResponse.BANDSTOP):
                    wp = normalized_cutoff
                    ws = [wp[0] * 0.8, wp[1] * 1.2]  # Approximate stopband
                else:
                    wp = normalized_cutoff[0]
                    ws = wp * 1.5 if spec.response_type == FilterResponse.LOWPASS else wp * 0.67
                
                order, _ = signal.buttord(wp, ws, spec.ripple_db, spec.attenuation_db)
                return min(order, self._max_order)
            
            elif spec.filter_type == FilterType.ELLIPTIC:
                # Use ellipord for order estimation
                if spec.response_type in (FilterResponse.BANDPASS, FilterResponse.BANDSTOP):
                    wp = normalized_cutoff
                    ws = [wp[0] * 0.8, wp[1] * 1.2]
                else:
                    wp = normalized_cutoff[0]
                    ws = wp * 1.5 if spec.response_type == FilterResponse.LOWPASS else wp * 0.67
                
                order, _ = signal.ellipord(wp, ws, spec.ripple_db, spec.attenuation_db)
                return min(order, self._max_order)
            
            else:
                # Conservative estimate for other filter types
                return min(spec.order, self._max_order)
                
        except Exception as e:
            logger.warning(f"Order estimation failed: {e}, using specified order")
            return spec.order
    
    def _design_butterworth(self, spec: FilterSpecification) -> FilterCoefficients:
        """Design Butterworth filter using scipy.signal.butter"""
        nyquist = spec.sample_rate / 2
        normalized_cutoff = np.array(spec.cutoff_frequencies) / nyquist
        
        # Ensure normalized frequencies are valid
        normalized_cutoff = np.clip(normalized_cutoff, 0.001, 0.999)
        
        b, a = signal.butter(
            spec.order,
            normalized_cutoff,
            btype=spec.response_type.value,
            analog=False,
            output='ba'
        )
        
        return FilterCoefficients(numerator=b, denominator=a)
    
    def _design_chebyshev1(self, spec: FilterSpecification) -> FilterCoefficients:
        """Design Chebyshev Type I filter using scipy.signal.cheby1"""
        nyquist = spec.sample_rate / 2
        normalized_cutoff = np.array(spec.cutoff_frequencies) / nyquist
        normalized_cutoff = np.clip(normalized_cutoff, 0.001, 0.999)
        
        b, a = signal.cheby1(
            spec.order,
            spec.ripple_db,
            normalized_cutoff,
            btype=spec.response_type.value,
            analog=False,
            output='ba'
        )
        
        return FilterCoefficients(numerator=b, denominator=a)
    
    def _design_chebyshev2(self, spec: FilterSpecification) -> FilterCoefficients:
        """Design Chebyshev Type II filter using scipy.signal.cheby2"""
        nyquist = spec.sample_rate / 2
        normalized_cutoff = np.array(spec.cutoff_frequencies) / nyquist
        normalized_cutoff = np.clip(normalized_cutoff, 0.001, 0.999)
        
        b, a = signal.cheby2(
            spec.order,
            spec.attenuation_db,
            normalized_cutoff,
            btype=spec.response_type.value,
            analog=False,
            output='ba'
        )
        
        return FilterCoefficients(numerator=b, denominator=a)
    
    def _design_elliptic(self, spec: FilterSpecification) -> FilterCoefficients:
        """Design elliptic filter using scipy.signal.ellip"""
        nyquist = spec.sample_rate / 2
        normalized_cutoff = np.array(spec.cutoff_frequencies) / nyquist
        normalized_cutoff = np.clip(normalized_cutoff, 0.001, 0.999)
        
        b, a = signal.ellip(
            spec.order,
            spec.ripple_db,
            spec.attenuation_db,
            normalized_cutoff,
            btype=spec.response_type.value,
            analog=False,
            output='ba'
        )
        
        return FilterCoefficients(numerator=b, denominator=a)
    
    def _design_bessel(self, spec: FilterSpecification) -> FilterCoefficients:
        """Design Bessel filter using scipy.signal.bessel"""
        nyquist = spec.sample_rate / 2
        normalized_cutoff = np.array(spec.cutoff_frequencies) / nyquist
        normalized_cutoff = np.clip(normalized_cutoff, 0.001, 0.999)
        
        b, a = signal.bessel(
            spec.order,
            normalized_cutoff,
            btype=spec.response_type.value,
            analog=False,
            output='ba'
        )
        
        return FilterCoefficients(numerator=b, denominator=a)
    
    def _design_fir(self, spec: FilterSpecification) -> FilterCoefficients:
        """Design FIR filter using scipy.signal.firwin"""
        nyquist = spec.sample_rate / 2
        normalized_cutoff = np.array(spec.cutoff_frequencies) / nyquist
        normalized_cutoff = np.clip(normalized_cutoff, 0.001, 0.999)
        
        # FIR filter design
        if spec.response_type == FilterResponse.LOWPASS:
            b = signal.firwin(spec.order + 1, normalized_cutoff[0])
        elif spec.response_type == FilterResponse.HIGHPASS:
            b = signal.firwin(spec.order + 1, normalized_cutoff[0], pass_zero=False)
        elif spec.response_type == FilterResponse.BANDPASS:
            b = signal.firwin(spec.order + 1, normalized_cutoff, pass_zero=False)
        elif spec.response_type == FilterResponse.BANDSTOP:
            b = signal.firwin(spec.order + 1, normalized_cutoff)
        else:
            raise UnsupportedFilterTypeError(f"FIR {spec.response_type.value} not supported")
        
        # FIR filters have denominator = [1]
        a = np.array([1.0])
        
        return FilterCoefficients(numerator=b, denominator=a)
    
    def _validate_stability(self, coefficients: FilterCoefficients) -> None:
        """
        Validate filter stability by checking pole locations.
        
        Args:
            coefficients: Filter coefficients to validate
            
        Raises:
            FilterInstabilityError: If filter is unstable
        """
        try:
            # Get poles from denominator
            poles = np.roots(coefficients.denominator)
            
            # Check if all poles are inside unit circle
            pole_magnitudes = np.abs(poles)
            max_pole_magnitude = np.max(pole_magnitudes)
            
            if max_pole_magnitude >= self._stability_margin:
                unstable_poles = poles[pole_magnitudes >= self._stability_margin]
                raise FilterInstabilityError(
                    f"Filter is unstable. Poles outside stability margin: {unstable_poles}"
                )
            
            logger.debug(f"Filter is stable. Max pole magnitude: {max_pole_magnitude:.6f}")
            
        except FilterInstabilityError:
            raise
        except Exception as e:
            logger.warning(f"Could not validate stability: {e}")


class FilterDesignService:
    """
    Domain service for filter design operations with caching and optimization.
    
    Provides high-level filter design operations with intelligent caching
    and performance optimization.
    """
    
    def __init__(self, designer: IFilterDesigner):
        """
        Initialize filter design service.
        
        Args:
            designer: Filter designer implementation
        """
        self._designer = designer
        self._coefficient_cache: Dict[str, FilterCoefficients] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        logger.info("FilterDesignService initialized")
    
    def get_or_create_filter(self, spec: FilterSpecification) -> FilterCoefficients:
        """
        Get cached filter coefficients or create new ones.
        
        Args:
            spec: Filter specification
            
        Returns:
            Filter coefficients (cached or newly designed)
        """
        cache_key = self._generate_cache_key(spec)
        
        if cache_key in self._coefficient_cache:
            self._cache_hits += 1
            logger.debug(f"Cache hit for filter: {cache_key}")
            return self._coefficient_cache[cache_key]
        
        # Cache miss - design new filter
        self._cache_misses += 1
        logger.debug(f"Cache miss for filter: {cache_key}")
        
        coefficients = self._designer.design_filter(spec)
        self._coefficient_cache[cache_key] = coefficients
        
        return coefficients
    
    def create_eq_filter_bank(self, bands: list, sample_rate: float) -> list:
        """
        Create filter bank for parametric EQ (placeholder for now).
        
        Args:
            bands: List of frequency bands
            sample_rate: Audio sample rate
            
        Returns:
            List of filter coefficients for each band
        """
        # This will be implemented when we create the EQ system
        logger.info(f"Creating EQ filter bank with {len(bands)} bands at {sample_rate} Hz")
        return []
    
    def clear_cache(self) -> None:
        """Clear filter coefficient cache and reset statistics"""
        cache_size = len(self._coefficient_cache)
        self._coefficient_cache.clear()
        
        logger.info(f"Cleared filter cache ({cache_size} entries). "
                   f"Cache stats: {self._cache_hits} hits, {self._cache_misses} misses")
        
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_size': len(self._coefficient_cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate_percent': round(hit_rate, 2)
        }
    
    def _generate_cache_key(self, spec: FilterSpecification) -> str:
        """
        Generate unique cache key for filter specification.
        
        Args:
            spec: Filter specification
            
        Returns:
            Unique cache key string
        """
        # Create deterministic string representation
        key_data = (
            spec.filter_type.value,
            spec.response_type.value,
            spec.cutoff_frequencies,
            spec.sample_rate,
            spec.order,
            spec.ripple_db,
            spec.attenuation_db
        )
        
        # Generate hash for efficient lookup
        key_string = str(key_data)
        return hashlib.md5(key_string.encode()).hexdigest()
