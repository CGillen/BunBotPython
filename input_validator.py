"""
Input validation and sanitization for BunBot favorites system.
Provides security-focused validation for user inputs.
"""

import re
import logging
from typing import Dict, Any, Optional
import validators

logger = logging.getLogger('discord')

class InputValidator:
    """Validates and sanitizes user inputs for security"""
    
    # Maximum lengths for various inputs
    MAX_STATION_NAME_LENGTH = 100
    MAX_URL_LENGTH = 2048
    MAX_SEARCH_TERM_LENGTH = 50
    
    # Allowed characters for station names (alphanumeric, spaces, common punctuation)
    STATION_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!()&\'"]+$')
    
    def __init__(self):
        pass
    
    def validate_url(self, url: str) -> Dict[str, Any]:
        """
        Validate and sanitize a stream URL
        
        Args:
            url: URL to validate
            
        Returns:
            Dict with 'valid', 'sanitized_url', 'error' keys
        """
        if not url:
            return {
                'valid': False,
                'sanitized_url': None,
                'error': 'URL cannot be empty'
            }
        
        # Remove leading/trailing whitespace
        url = url.strip()
        
        # Check length
        if len(url) > self.MAX_URL_LENGTH:
            return {
                'valid': False,
                'sanitized_url': None,
                'error': f'URL too long (max {self.MAX_URL_LENGTH} characters)'
            }
        
        # Validate URL format
        if not validators.url(url):
            return {
                'valid': False,
                'sanitized_url': None,
                'error': 'Invalid URL format'
            }
        
        # Check for allowed protocols
        allowed_protocols = ['http', 'https']
        protocol = url.split('://')[0].lower()
        if protocol not in allowed_protocols:
            return {
                'valid': False,
                'sanitized_url': None,
                'error': f'Protocol not allowed. Use: {", ".join(allowed_protocols)}'
            }
        
        # Basic security checks
        if self._contains_suspicious_patterns(url):
            return {
                'valid': False,
                'sanitized_url': None,
                'error': 'URL contains suspicious patterns'
            }
        
        return {
            'valid': True,
            'sanitized_url': url,
            'error': None
        }
    
    def validate_station_name(self, name: str) -> Dict[str, Any]:
        """
        Validate and sanitize a station name
        
        Args:
            name: Station name to validate
            
        Returns:
            Dict with 'valid', 'sanitized_name', 'error' keys
        """
        if not name:
            return {
                'valid': False,
                'sanitized_name': None,
                'error': 'Station name cannot be empty'
            }
        
        # Remove leading/trailing whitespace and normalize
        name = name.strip()
        
        # Check length
        if len(name) > self.MAX_STATION_NAME_LENGTH:
            return {
                'valid': False,
                'sanitized_name': None,
                'error': f'Station name too long (max {self.MAX_STATION_NAME_LENGTH} characters)'
            }
        
        # Check for allowed characters
        if not self.STATION_NAME_PATTERN.match(name):
            return {
                'valid': False,
                'sanitized_name': None,
                'error': 'Station name contains invalid characters'
            }
        
        # Remove excessive whitespace
        sanitized_name = re.sub(r'\s+', ' ', name)
        
        return {
            'valid': True,
            'sanitized_name': sanitized_name,
            'error': None
        }
    
    def validate_search_term(self, search_term: str) -> Dict[str, Any]:
        """
        Validate and sanitize a search term
        
        Args:
            search_term: Search term to validate
            
        Returns:
            Dict with 'valid', 'sanitized_term', 'error' keys
        """
        if not search_term:
            return {
                'valid': False,
                'sanitized_term': None,
                'error': 'Search term cannot be empty'
            }
        
        # Remove leading/trailing whitespace
        search_term = search_term.strip()
        
        # Check length
        if len(search_term) > self.MAX_SEARCH_TERM_LENGTH:
            return {
                'valid': False,
                'sanitized_term': None,
                'error': f'Search term too long (max {self.MAX_SEARCH_TERM_LENGTH} characters)'
            }
        
        # Basic sanitization - remove SQL wildcards that could be abused
        sanitized_term = search_term.replace('%', '').replace('_', '')
        
        # Remove excessive whitespace
        sanitized_term = re.sub(r'\s+', ' ', sanitized_term)
        
        if not sanitized_term:
            return {
                'valid': False,
                'sanitized_term': None,
                'error': 'Search term contains only invalid characters'
            }
        
        return {
            'valid': True,
            'sanitized_term': sanitized_term,
            'error': None
        }
    
    def validate_favorite_number(self, number: int) -> Dict[str, Any]:
        """
        Validate a favorite number
        
        Args:
            number: Favorite number to validate
            
        Returns:
            Dict with 'valid', 'error' keys
        """
        if not isinstance(number, int):
            return {
                'valid': False,
                'error': 'Favorite number must be an integer'
            }
        
        if number < 1:
            return {
                'valid': False,
                'error': 'Favorite number must be positive'
            }
        
        if number > 9999:  # Reasonable upper limit
            return {
                'valid': False,
                'error': 'Favorite number too large (max 9999)'
            }
        
        return {
            'valid': True,
            'error': None
        }
    
    def validate_role_name(self, role_name: str) -> Dict[str, Any]:
        """
        Validate a permission role name
        
        Args:
            role_name: Role name to validate
            
        Returns:
            Dict with 'valid', 'sanitized_name', 'error' keys
        """
        if not role_name:
            return {
                'valid': False,
                'sanitized_name': None,
                'error': 'Role name cannot be empty'
            }
        
        # Normalize to lowercase
        role_name = role_name.strip().lower()
        
        # Whitelist valid role names
        valid_roles = {'user', 'dj', 'radio manager', 'admin'}
        
        if role_name not in valid_roles:
            return {
                'valid': False,
                'sanitized_name': None,
                'error': f'Invalid role name. Valid options: {", ".join(valid_roles)}'
            }
        
        return {
            'valid': True,
            'sanitized_name': role_name,
            'error': None
        }
    
    def _contains_suspicious_patterns(self, url: str) -> bool:
        """
        Check for suspicious patterns in URLs that might indicate attacks
        
        Args:
            url: URL to check
            
        Returns:
            True if suspicious patterns found
        """
        suspicious_patterns = [
            # SQL injection attempts
            r'(\bUNION\b|\bSELECT\b|\bINSERT\b|\bDELETE\b|\bDROP\b)',
            # Script injection
            r'(<script|javascript:|data:)',
            # Path traversal
            r'(\.\./|\.\.\\)',
            # Null bytes
            r'%00',
        ]
        
        url_lower = url.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, url_lower, re.IGNORECASE):
                logger.warning(f"Suspicious pattern detected in URL: {pattern}")
                return True
        
        return False

# Global input validator instance
_input_validator = None

def get_input_validator() -> InputValidator:
    """Get global input validator instance"""
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator
