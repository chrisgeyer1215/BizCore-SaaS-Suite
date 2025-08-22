# ============================================================================
# backend/apps/crm/permissions/ip_based.py - IP and Location-Based Access Control
# ============================================================================

import ipaddress
import requests
import json
from typing import Dict, List, Any, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
import logging

from .base import ObjectLevelPermission

logger = logging.getLogger(__name__)


class IPBasedPermission(ObjectLevelPermission):
    """
    IP address and network-based access control with geographic restrictions
    """
    
    # IP access control configuration
    IP_ACCESS_CONFIG = {
        'default': {
            'whitelist_enabled': False,
            'blacklist_enabled': True,
            'geo_restrictions_enabled': False,
            'vpn_detection_enabled': True,
            'tor_detection_enabled': True,
            'max_countries_per_user': 3
        },
        'SYSTEM_ADMIN': {
            'whitelist_enabled': False,
            'blacklist_enabled': True,
            'geo_restrictions_enabled': False,
            'vpn_detection_enabled': False,  # Admins may use VPN
            'tor_detection_enabled': True,
            'emergency_access_enabled': True
        },
        'TENANT_ADMIN': {
            'whitelist_enabled': True,
            'blacklist_enabled': True,
            'geo_restrictions_enabled': True,
            'vpn_detection_enabled': False,
            'tor_detection_enabled': True,
            'allowed_countries': ['US', 'CA', 'GB', 'AU']
        },
        'FINANCE': {
            'whitelist_enabled': True,
            'blacklist_enabled': True,
            'geo_restrictions_enabled': True,
            'vpn_detection_enabled': True,
            'tor_detection_enabled': True,
            'allowed_countries': ['US'],  # Strict geo-restrictions
            'office_ip_required': True
        },
        'COMPLIANCE_OFFICER': {
            'whitelist_enabled': True,
            'blacklist_enabled': True,
            'geo_restrictions_enabled': True,
            'vpn_detection_enabled': True,
            'tor_detection_enabled': True,
            'allowed_countries': ['US'],
            'office_ip_required': True,
            'high_security_mode': True
        }
    }
    
    # Known IP ranges and classifications
    IP_CLASSIFICATIONS = {
        'corporate_networks': [
            '10.0.0.0/8',
            '172.16.0.0/12',
            '192.168.0.0/16'
        ],
        'cloud_providers': [
            '3.0.0.0/8',      # Amazon AWS
            '8.8.8.0/24',     # Google
            '13.107.42.14/32' # Microsoft
        ],
        'high_risk_countries': [
            'CN', 'RU', 'KP', 'IR', 'SY'  # Example high-risk countries
        ],
        'blocked_regions': [
            'Crimea', 'Donetsk', 'Luhansk'  # Sanctioned regions
        ]
    }
    
    def has_permission(self, request, view) -> bool:
        """Enhanced permission check with IP-based validation"""
        try:
            # Parent permission check
            if not super().has_permission(request, view):
                return False
            
            # Get client IP and user roles
            client_ip = self._get_client_ip(request)
            user_roles = getattr(request, 'user_roles', [])
            
            # Get IP access configuration
            ip_config = self._get_ip_access_config(user_roles)
            
            # Check IP whitelist
            if ip_config.get('whitelist_enabled') and not self._check_ip_whitelist(client_ip, request.user):
                self._log_ip_denial(request, 'whitelist_violation', client_ip)
                return False
            
            # Check IP blacklist
            if ip_config.get('blacklist_enabled') and self._check_ip_blacklist(client_ip):
                self._log_ip_denial(request, 'blacklist_violation', client_ip)
                return False
            
            # Check geographic restrictions
            if ip_config.get('geo_restrictions_enabled') and not self._check_geographic_access(client_ip, ip_config):
                self._log_ip_denial(request, 'geographic_restriction', client_ip)
                return False
            
            # Check for VPN usage
            if ip_config.get('vpn_detection_enabled') and self._detect_vpn_usage(client_ip):
                self._log_ip_denial(request, 'vpn_detected', client_ip)
                return False
            
            # Check for Tor usage
            if ip_config.get('tor_detection_enabled') and self._detect_tor_usage(client_ip):
                self._log_ip_denial(request, 'tor_detected', client_ip)
                return False
            
            # Check office IP requirement
            if ip_config.get('office_ip_required') and not self._check_office_ip(client_ip, request.user):
                # Allow if emergency access is enabled and justified
                if not (ip_config.get('emergency_access_enabled') and self._check_emergency_access(request)):
                    self._log_ip_denial(request, 'office_ip_required', client_ip)
                    return False
            
            # Track IP usage patterns
            self._track_ip_usage(request, client_ip)
            
            return True
            
        except Exception as e:
            logger.error(f"IP-based permission check failed: {e}", exc_info=True)
            return False
    
    def _get_ip_access_config(self, user_roles: List[str]) -> Dict:
        """Get IP access configuration for user roles"""
        try:
            # Start with default config
            config = self.IP_ACCESS_CONFIG['default'].copy()
            
            # Apply role-specific configurations (most restrictive wins)
            restriction_priority = [
                'COMPLIANCE_OFFICER', 'FINANCE', 'TENANT_ADMIN', 'SYSTEM_ADMIN'
            ]
            
            for role in restriction_priority:
                if role in user_roles and role in self.IP_ACCESS_CONFIG:
                    role_config = self.IP_ACCESS_CONFIG[role]
                    config.update(role_config)
                    break
            
            return config
            
        except Exception as e:
            logger.error(f"Getting IP access config failed: {e}")
            return self.IP_ACCESS_CONFIG['default']
    
    def _check_ip_whitelist(self, client_ip: str, user) -> bool:
        """Check if IP is in user's whitelist"""
        try:
            # Get user's IP whitelist
            whitelist = self._get_user_ip_whitelist(user)
            
            if not whitelist:
                return True  # No whitelist configured
            
            client_ip_obj = ipaddress.ip_address(client_ip)
            
            for allowed_ip in whitelist:
                try:
                    # Handle single IPs and CIDR ranges
                    if '/' in allowed_ip:
                        network = ipaddress.ip_network(allowed_ip, strict=False)
                        if client_ip_obj in network:
                            return True
                    else:
                        if client_ip_obj == ipaddress.ip_address(allowed_ip):
                            return True
                except ValueError:
                    logger.warning(f"Invalid IP in whitelist: {allowed_ip}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"IP whitelist check failed: {e}")
            return True  # Default to allow on error
    
    def _check_ip_blacklist(self, client_ip: str) -> bool:
        """Check if IP is in global blacklist"""
        try:
            # Get global IP blacklist
            blacklist = self._get_global_ip_blacklist()
            
            if not blacklist:
                return False  # No blacklist configured
            
            client_ip_obj = ipaddress.ip_address(client_ip)
            
            for blocked_ip in blacklist:
                try:
                    if '/' in blocked_ip:
                        network = ipaddress.ip_network(blocked_ip, strict=False)
                        if client_ip_obj in network:
                            return True
                    else:
                        if client_ip_obj == ipaddress.ip_address(blocked_ip):
                            return True
                except ValueError:
                    logger.warning(f"Invalid IP in blacklist: {blocked_ip}")
                    continue
            
            # Check against threat intelligence feeds
            if self._check_threat_intelligence(client_ip):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"IP blacklist check failed: {e}")
            return False
    
    def _check_geographic_access(self, client_ip: str, ip_config: Dict) -> bool:
        """Check geographic restrictions based on IP location"""
        try:
            # Get IP geolocation
            geo_info = self._get_ip_geolocation(client_ip)
            
            if not geo_info:
                return True  # Allow if geolocation unavailable
            
            country_code = geo_info.get('country_code', '')
            region = geo_info.get('region', '')
            
            # Check allowed countries
            allowed_countries = ip_config.get('allowed_countries', [])
            if allowed_countries and country_code not in allowed_countries:
                return False
            
            # Check high-risk countries
            if country_code in self.IP_CLASSIFICATIONS['high_risk_countries']:
                # High-risk countries require additional validation
                if not self._validate_high_risk_access(client_ip, country_code):
                    return False
            
            # Check blocked regions
            if region in self.IP_CLASSIFICATIONS['blocked_regions']:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Geographic access check failed: {e}")
            return True
    
    def _detect_vpn_usage(self, client_ip: str) -> bool:
        """Detect if IP is from a VPN service"""
        try:
            # Check against known VPN IP ranges
            vpn_indicators = self._check_vpn_indicators(client_ip)
            
            if vpn_indicators['is_vpn']:
                return True
            
            # Additional VPN detection methods
            if self._check_vpn_services_api(client_ip):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"VPN detection failed: {e}")
            return False
    
    def _detect_tor_usage(self, client_ip: str) -> bool:
        """Detect if IP is from Tor network"""
        try:
            # Check against Tor exit node lists
            return self._check_tor_exit_nodes(client_ip)
            
        except Exception as e:
            logger.error(f"Tor detection failed: {e}")
            return False
    
    def _check_office_ip(self, client_ip: str, user) -> bool:
        """Check if IP is from user's office location"""
        try:
            # Get user's office IP ranges
            office_ips = self._get_user_office_ips(user)
            
            if not office_ips:
                return False  # No office IPs configured
            
            client_ip_obj = ipaddress.ip_address(client_ip)
            
            for office_ip in office_ips:
                try:
                    if '/' in office_ip:
                        network = ipaddress.ip_network(office_ip, strict=False)
                        if client_ip_obj in network:
                            return True
                    else:
                        if client_ip_obj == ipaddress.ip_address(office_ip):
                            return True
                except ValueError:
                    logger.warning(f"Invalid office IP: {office_ip}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Office IP check failed: {e}")
            return False
    
    def _get_ip_geolocation(self, ip_address: str) -> Optional[Dict]:
        """Get IP geolocation information"""
        try:
            # Check cache first
            cache_key = f"ip_geo_{ip_address}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Use a geolocation service (placeholder implementation)
            # In production, you'd integrate with services like MaxMind, IPStack, etc.
            geo_data = {
                'country_code': 'US',  # Placeholder
                'country_name': 'United States',
                'region': 'California',
                'city': 'San Francisco',
                'latitude': 37.7749,
                'longitude': -122.4194,
                'timezone': 'America/Los_Angeles',
                'isp': 'Example ISP'
            }
            
            # Cache result for 24 hours
            cache.set(cache_key, geo_data, 86400)
            
            return geo_data
            
        except Exception as e:
            logger.error(f"IP geolocation failed: {e}")
            return None
    
    def _check_vpn_indicators(self, ip_address: str) -> Dict:
        """Check for VPN indicators"""
        try:
            # Implement VPN detection logic
            # This would integrate with commercial VPN detection services
            return {
                'is_vpn': False,
                'vpn_service': None,
                'confidence': 0.0
            }
            
        except Exception as e:
            logger.error(f"VPN indicator check failed: {e}")
            return {'is_vpn': False}
    
    def _check_tor_exit_nodes(self, ip_address: str) -> bool:
        """Check if IP is a Tor exit node"""
        try:
            # Check against Tor exit node list
            # This would integrate with Tor Project's exit node lists
            return False
            
        except Exception as e:
            logger.error(f"Tor exit node check failed: {e}")
            return False
    
    def _get_user_ip_whitelist(self, user) -> List[str]:
        """Get user's IP whitelist"""
        try:
            # This would be stored in user profile or tenant settings
            if hasattr(user, 'ip_whitelist'):
                return user.ip_whitelist
            
            # Check tenant-level whitelist
            if hasattr(user, 'tenant') and hasattr(user.tenant, 'ip_whitelist'):
                return user.tenant.ip_whitelist
            
            return []
            
        except Exception as e:
            logger.error(f"Getting user IP whitelist failed: {e}")
            return []
    
    def _get_global_ip_blacklist(self) -> List[str]:
        """Get global IP blacklist"""
        try:
            # This would integrate with threat intelligence feeds
            return [
                '192.0.2.0/24',  # Example blocked range
                '198.51.100.0/24'
            ]
            
        except Exception as e:
            logger.error(f"Getting global IP blacklist failed: {e}")
            return []
    
    def _track_ip_usage(self, request, client_ip: str):
        """Track IP usage patterns for analysis"""
        try:
            from ..models import IPAccessLog
            
            # Log IP access
            IPAccessLog.objects.create(
                user=request.user,
                tenant=getattr(request, 'tenant', None),
                ip_address=client_ip,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                access_time=timezone.now(),
                path=request.path,
                method=request.method,
                geo_location=self._get_ip_geolocation(client_ip)
            )
            
        except Exception as e:
            logger.error(f"IP usage tracking failed: {e}")
    
    def _log_ip_denial(self, request, reason: str, client_ip: str):
        """Log IP-based access denial"""
        try:
            denial_event = {
                'event_type': 'IP_BASED_ACCESS_DENIAL',
                'reason': reason,
                'client_ip': client_ip,
                'user_id': request.user.id if request.user else None,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'timestamp': timezone.now().isoformat(),
                'path': request.path,
                'method': request.method,
                'geo_location': self._get_ip_geolocation(client_ip)
            }
            
            logger.warning(f"IP-based access denied: {denial_event}")
            
        except Exception as e:
            logger.error(f"IP denial logging failed: {e}")


class GeoLocationPermission(IPBasedPermission):
    """
    Enhanced geographic-based access control with advanced location intelligence
    """
    
    def has_permission(self, request, view) -> bool:
        """Geographic permission check with location intelligence"""
        try:
            # Parent IP-based checks
            if not super().has_permission(request, view):
                return False
            
            # Enhanced geographic validation
            if not self._validate_geographic_context(request):
                return False
            
            # Check location-based business rules
            if not self._check_location_business_rules(request, view):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Geolocation permission check failed: {e}")
            return False
    
    def _validate_geographic_context(self, request) -> bool:
        """Validate geographic context with advanced checks"""
        try:
            client_ip = self._get_client_ip(request)
            geo_info = self._get_ip_geolocation(client_ip)
            
            if not geo_info:
                return True
            
            # Check for impossible travel
            if not self._check_impossible_travel(request, geo_info):
                self._log_ip_denial(request, 'impossible_travel', client_ip)
                return False
            
            # Check for high-risk locations
            if self._is_high_risk_location(geo_info):
                if not self._validate_high_risk_access(client_ip, geo_info['country_code']):
                    self._log_ip_denial(request, 'high_risk_location', client_ip)
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Geographic context validation failed: {e}")
            return True
    
    def _check_impossible_travel(self, request, current_geo: Dict) -> bool:
        """Check for impossible travel scenarios"""
        try:
            user_id = request.user.id
            
            # Get last known location
            last_location = self._get_last_user_location(user_id)
            
            if not last_location:
                return True  # First access
            
            # Calculate distance and time difference
            distance_km = self._calculate_distance(
                last_location['latitude'], last_location['longitude'],
                current_geo['latitude'], current_geo['longitude']
            )
            
            time_diff_hours = (timezone.now() - last_location['timestamp']).total_seconds() / 3600
            
            # Maximum realistic travel speed (including flight time)
            max_speed_kmh = 1000  # ~600 mph average including airports
            
            if time_diff_hours > 0:
                required_speed = distance_km / time_diff_hours
                
                if required_speed > max_speed_kmh:
                    logger.warning(f"Impossible travel detected: {distance_km}km in {time_diff_hours}h "
                                 f"(requires {required_speed:.1f} km/h)")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Impossible travel check failed: {e}")
            return True
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        try:
            import math
            
            # Convert to radians
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            
            # Haversine formula
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            r = 6371  # Earth's radius in kilometers
            
            return c * r
            
        except Exception as e:
            logger.error(f"Distance calculation failed: {e}")
            return 0.0
    
    def _is_high_risk_location(self, geo_info: Dict) -> bool:
        """Check if location is considered high risk"""
        try:
            country_code = geo_info.get('country_code', '')
            region = geo_info.get('region', '')
            
            # Check high-risk countries
            if country_code in self.IP_CLASSIFICATIONS['high_risk_countries']:
                return True
            
            # Check blocked regions
            if region in self.IP_CLASSIFICATIONS['blocked_regions']:
                return True
            
            # Check for other risk factors
            isp = geo_info.get('isp', '').lower()
            high_risk_isps = ['hosting', 'datacenter', 'proxy', 'vpn']
            
            if any(risk_term in isp for risk_term in high_risk_isps):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"High-risk location check failed: {e}")
            return False