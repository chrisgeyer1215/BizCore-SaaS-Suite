# apps/ecommerce/domain/value_objects/seo.py
"""
SEO Value Objects
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
import re


@dataclass(frozen=True)
class SE object"""
    title: str
    description: str
    keywords: Optional[str] = None
    canonical_url: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: str = "product"
    twitter_card: str = "summary_large_image"
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    twitter_image: Optional[str] = None
    meta_robots: str = "index,[Dict] = None
    
    def __post_init__(self):
        # Validation
        if len(self.title) > 60:
            raise ValueError("SEO title should not exceed 60 characters")
        
        if len(self.description) > 160:
            raise ValueError("SEO description should not exceed 160 characters")
        
        if self.canonical_url and not self._is_valid_url(self.canonical_url):
            raise ValueError("Invalid canonical URL format")
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    def get_open_graph_tags(self) -> Dict[str, str]:
        """Get Open Graph meta tags"""
        tags = {
            "og:title": self.og_title or self.title,
            "og:description": self.og_description or self.description,
            "og:type": self.og_type,
        }
        
        if self.og_image:
            tags["og:image"] = self.og_image
        
        if self.canonical_url:
            tags["og:url"] = self.canonical_url
        
        return {k: v for k, v in tags.items() if v}
    
    def get_twitter_tags(self) -> Dict[str, str]:
        """Get Twitter Card meta tags"""
        tags = {
            "twitter:card": self.twitter_card,
            "twitter:title": self.twitter_title or self.title,
            "twitter:description": self.twitter_description or self.description,
        }
        
        if self.twitter_image:
            tags["twitter:image"] = self.twitter_image
        
        return {k: v for k, v in tags.items() if v}
    
    def get_structured_data(self) -> Dict:
        """Get structured data for JSON
            return self.structured_data
        
        # Default product structured data
        return {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": self.title,
            "description": self.description
        }


@dataclass(frozen=True)  
class URLSlug:
    """URL slug value object"""
    value: str
    
    def __post_init__(self):
        if not self._is_valid_slug(self.value):
            raise ValueError("Invalid URL slug format")
    
    def _is_valid_slug(self, slug: str) -> bool:
        """Validate slug format"""
        slug_pattern = re.compile(r'^[a-z0-9-]+$')
        return (
            slug_pattern.match(slug) and
            not slug.startswith('-') and 
            not slug.endswith('-') and
            '--' not in slug and
            len(slug) <= 100
        )
    
    def __str__(self):
        return self.value


@dataclass
class SEOAnalysis:
    """SEO analysis results"""
    score: float  # 0-100
    issues: List[str]
    recommendations: List[str]
    keyword_density: Dict[str, float]
    readability_score: float
    
    @property
    def grade(self) -> str:
        """Get SEO grade"""
        if self.score >= 90:
            return "A+"
        elif self.score >= 80:
            return "A"
        elif self.score >= 70:
            return "B"
        elif self.score >= 60:
            return "C"
        else:
            return "F"