# apps/ecommerce/domain/services/seo_service.py
"""
SEO Domain Service
"""

from typing import List, Dict, Optional
import re
from collections import Counter

from ..entities.product import Product
from ..value_objects.seo import SEOMetadata, SEOAnalysis
from .base import BaseDomainService


class SEOService(BaseDomainService):
    """Service for SEO operations and analysis"""
    
    def analyze_product_seo(self, product: Product) -> SEOAnalysis:
        """Analyze product SEO and provide recommendations"""
        issues = []
        recommendations = []
        score = 100.0
        
        seo_data = product.seo_metadata
        
        if SEOAnalysis(
                score=0,
                issues=["No SEO data configured"],
                recommendations=["Add SEO title, description, and keywords"],
                keyword_density={},
                readability_score=0
            )
        
        # Title analysis
        title_analysis = self._analyze_title(seo_data.title, product.title)
        issues.extend(title_analysis['issues'])
        recommendations.extend(title_analysis['recommendations'])
        score -= title_analysis['penalty']
        
        # Description analysis
        desc_analysis = self._analyze_description(seo_data.description, product.description)
        issues.extend(desc_analysis['issues'])
        recommendations.extend(desc_analysis['recommendations'])
        score -= desc_analysis['penalty']
        
        # Keywords analysis
        keyword_analysis = self._analyze_keywords(seo_data.keywords, product)
        issues.extend(keyword_analysis['issues'])
        recommendations.extend(keyword_analysis['recommendations'])
        score -= keyword_analysis['penalty']
        
        # URL analysis
        url_analysis = self._analyze_url(str(product.url_slug))
        issues.extend(url_analysis['issues'])
        recommendations.extend(url_analysis['recommendations'])
        score -= url_analysis['penalty']
        
        # Content analysis
        content_analysis = self._analyze_content(product)
        keyword_density = content_analysis['keyword_density']
        readability_score = content_analysis['readability_score']
        
        return SEOAnalysis(
            score=max(0, score),
            issues=issues,
            recommendations=recommendations,
            keyword_density=keyword_density,
            readability_score=readability_score
        )
    
    def _analyze_title(self, seo_title: str, product_title: str) -> Dict:
        """Analyze SEO title"""
        issues = []
        recommendations = []
        penalty = 0
        
        if not seo_title:
            issues.append("Missing SEO title")
            recommendations.append("Add a descriptive SEO title")
            penalty += 20
        else:
            if len(seo_title) < 30:
                issues.append("SEO title too short")
                recommendations.append("Expand SEO title to 30-60 characters")
                penalty += 10
            elif len(seo_title) > 60:
                issues.append("SEO title too long")
                recommendations.append("Shorten SEO title to under 60 characters")
                penalty += 15
            
            # Check if title contains brand/product name
            if product_title.lower() not in seo_title.lower():
                recommendations.append("Consider including product name in SEO title")
                penalty += 5
        
        return {'issues': issues, 'recommendations': recommendations, 'penalty': penalty}
    
    def _analyze_description(self, seo_description: str, product_description: str) -> Dict:
        """Analyze SEO description"""
        issues = []
        recommendations = []
        penalty = 0
        
        if not seo_description:
            issues.append("Missing SEO description")
            recommendations.append("Add a compelling SEO description")
            penalty += 20
        else:
            if len(seo_description) < 120:
                issues.append("SEO description too short")
                recommendations.append("Expand SEO description to 120-160 characters")
                penalty += 10
            elif len(seo_description) > 160:
                issues.append("SEO description too long")
                recommendations.append("Shorten SEO description to under 160 characters")
                penalty += 15
            
            # Check for call-to-action
            cta_words = ['buy', 'shop', 'get', 'order', 'purchase', 'discover']
            if not any(word in seo_description.lower() for word in cta_words):
                recommendations.append("Consider adding a call-to-action in description")
                penalty += 5
        
        return {'issues': issues, 'recommendations': recommendations, 'penalty': penalty}
    
    def _analyze_keywords(self, keywords: Optional[str], product: Product) -> Dict:
        """Analyze SEO keywords"""
        issues = []
        recommendations = []
        penalty = 0
        
        if not keywords:
            recommendations.append("Add relevant keywords for better SEO")
            penalty += 10
        else:
            keyword_list = [k.strip() for k in keywords.split(',')]
            
            if len(keyword_list) < 3:
                recommendations.append("Add more relevant keywords (aim for 5-10)")
                penalty += 5
            elif len(keyword_list) > 15:
                issues.append("Too many keywords - focus on most relevant")
                recommendations.append("Reduce keywords to 5-10 most relevant ones")
                penalty += 10
            
            # Check keyword relevance to product title/description
            product_text = f"{product.title} {product.description}".lower()
            irrelevant_keywords = [
                kw for kw in keyword_list 
                if kw.lower() not in product_text
            ]
            
            if len(irrelevant_keywords) > len(keyword_list) * 0.3:
                issues.append("Some keywords may not be relevant to product")
                recommendations.append("Ensure all keywords relate to the product")
                penalty += 8
        
        return {'issues': issues, 'recommendations': recommendations, 'penalty': penalty}
    
    def _analyze_url(self, url_slug: str) -> Dict:
        """Analyze URL structure"""
        issues = []
        recommendations = []
        penalty = 0
        
        if len(url_slug) > 75:
            issues.append("URL slug too long")
            recommendations.append("Shorten URL slug for better SEO")
            penalty += 10
        
        if '_' in url_slug:
            issues.append("URL contains underscores")
            recommendations.append("Use hyphens instead of underscores in URL")
            penalty += 5
        
        # Check for stop words
        stop_words = ['a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'in', 'is', 'it', 'of', 'on', 'that', 'the', 'to', 'was', 'will', 'with']
        slug_words = url_slug.split('-')
        if any(word in stop_words for word in slug_words):
            recommendations.append("Consider removing stop words from URL for cleaner structure")
            penalty += 3
        
        return {'issues': issues, 'recommendations': recommendations, 'penalty': penalty}
    
    def _analyze_content(self, product: Product) -> Dict:
        """Analyze product content for SEO"""
        content = f"{product.title} {product.description}"
        words = re.findall(r'\w+', content.lower())
        
        # Calculate keyword density
        word_count = len(words)
        word_freq = Counter(words)
        keyword_density = {
            word: (count / word_count) * 100 
            for word, count in word_freq.most_common(10)
        }
        
        # Simple readability score (Flesch Reading Ease approximation)
        sentences = len(re.findall(r'[.!?]+', product.description or ''))
        if sentences == 0:
            sentences = 1
        
        avg_sentence_length = word_count / sentences
        readability_score = 206.835 - (1.015 * avg_sentence_length)
        readability_score = max(0, min(100, readability_score))
        
        return {
            'keyword_density': keyword_density,
            'readability_score': readability_score
        }
    
    def generate_seo_suggestions(self, product: Product) -> SE suggestions for a product"""
        # Generate optimized SEO title
        seo_title = f"{product.title}"
        if product.brand:
            seo_title = f"{product.title} - {product.brand}"
        
        if len(seo_title) > 60:
            seo_title = product.title[:57] + "..."
        
        # Generate SEO description
        description = product.description or ""
        if len(description) > 160:
            seo_description = description[:157] + "..."
        else:
            seo_description = description
        
        # Generate keywords from title and description
        content = f"{product.title} {description}".lower()
        words = re.findall(r'\w+', content)
        word_freq = Counter(words)
        
        # Filter out common words and get meaningful keywords
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'a', 'an'}
        keywords = [
            word for word, count in word_freq.most_common(10)
            if len(word) > 3 and word not in stop_words
        ]
        
        return SEOMetadata(
            title=seo_title,
            description=seo_description,
            keywords=', '.join(keywords[:8]),
            og_title=seo_title,
            og_description=seo_description,
            og_type="product"
        )