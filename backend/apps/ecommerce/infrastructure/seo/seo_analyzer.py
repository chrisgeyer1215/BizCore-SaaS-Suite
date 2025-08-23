"""
Advanced SEO Analysis Infrastructure
"""

import asyncio
import aiohttp
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.cache import cache
from ...domain.value_objects.seo import SEOAnalysis, SEOMetadata
from ...domain.services.seo_service import SEOService


@dataclass
class CompetitorSEOData:
    """Competitor SEO analysis data"""
    domain: str
    title: str
    description: str
    keywords: List[str]
    h1_tags: List[str]
    schema_markup: Dict[str, Any]
    page_speed: float
    mobile_friendly: bool
    ssl_enabled: bool


@dataclass
class SEOAuditResult:
    """Comprehensive SEO audit result"""
    url: str
    score: float
    performance_score: float
    accessibility_score: float
    seo_score: float
    best_practices_score: float
    issues: List[Dict[str, Any]]
    opportunities: List[Dict[str, Any]]
    passed_audits: List[str]
    failed_audits: List[str]


class AdvancedSEOAnalyzer:
    """Advanced SEO analysis with external tools integration"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.seo_service = SEOService(tenant)
        self.google_api_key = settings.GOOGLE_API_KEY
        self.lighthouse_api_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        
    async def perform_comprehensive_audit(self, product_url: str) -> SEOAuditResult:
        """Perform comprehensive SEO audit using multiple tools"""
        try:
            # Run parallel audits
            lighthouse_task = self._run_lighthouse_audit(product_url)
            technical_task = self._run_technical_seo_audit(product_url)
            content_task = self._run_content_audit(product_url)
            
            lighthouse_result, technical_result, content_result = await asyncio.gather(
                lighthouse_task, technical_task, content_task,
                return_exceptions=True
            )
            
            # Combine results
            overall_score = self._calculate_overall_score(
                lighthouse_result, technical_result, content_result
            )
            
            issues = []
            opportunities = []
            passed_audits = []
            failed_audits = []
            
            # Process lighthouse results
            if isinstance(lighthouse_result, dict):
                issues.extend(lighthouse_result.get('issues', []))
                opportunities.extend(lighthouse_result.get('opportunities', []))
                passed_audits.extend(lighthouse_result.get('passed_audits', []))
                failed_audits.extend(lighthouse_result.get('failed_audits', []))
            
            # Process technical results
            if isinstance(technical_result, dict):
                issues.extend(technical_result.get('issues', []))
                opportunities.extend(technical_result.get('opportunities', []))
            
            # Process content results
            if isinstance(content_result, dict):
                issues.extend(content_result.get('issues', []))
                opportunities.extend(content_result.get('opportunities', []))
            
            return SEOAuditResult(
                url=product_url,
                score=overall_score,
                performance_score=lighthouse_result.get('performance_score', 0) if isinstance(lighthouse_result, dict) else 0,
                accessibility_score=lighthouse_result.get('accessibility_score', 0) if isinstance(lighthouse_result, dict) else 0,
                seo_score=lighthouse_result.get('seo_score', 0) if isinstance(lighthouse_result, dict) else 0,
                best_practices_score=lighthouse_result.get('best_practices_score', 0) if isinstance(lighthouse_result, dict) else 0,
                issues=issues,
                opportunities=opportunities,
                passed_audits=passed_audits,
                failed_audits=failed_audits
            )
            
        except Exception as e:
            # Return default audit result with error
            return SEOAuditResult(
                url=product_url,
                score=0,
                performance_score=0,
                accessibility_score=0,
                seo_score=0,
                best_practices_score=0,
                issues=[{"type": "error", "message": f"Audit failed: {str(e)}"}],
                opportunities=[],
                passed_audits=[],
                failed_audits=["comprehensive_audit"]
            )
    
    async def _run_lighthouse_audit(self, url: str) -> Dict[str, Any]:
        """Run Google Lighthouse audit"""
        try:
            params = {
                'url': url,
                'key': self.google_api_key,
                'category': ['performance', 'accessibility', 'best-practices', 'seo'],
                'strategy': 'desktop'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.lighthouse_api_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._process_lighthouse_results(data)
                    else:
                        return {"error": f"Lighthouse API returned {response.status}"}
                        
        except Exception as e:
            return {"error": f"Lighthouse audit failed: {str(e)}"}
    
    def]) -> Dict[str, Any]:
        """Process Lighthouse API response"""
        lighthouse_result = data.get('lighthouseResult', {})
        categories = lighthouse_result.get('categories', {})
        audits = lighthouse_result.get('audits', {})
        
        # Extract scores
        performance_score = categories.get('performance', {}).get('score', 0) * 100
        accessibility_score = categories.get('accessibility', {}).get('score', 0) * 100
        seo_score = categories.get('seo', {}).get('score', 0) * 100
        best_practices_score = categories.get('best-practices', {}).get('score', 0) * 100
        
        # Extract issues and opportunities
        issues = []
        opportunities = []
        passed_audits = []
        failed_audits = []
        
        for audit_id, audit_data in audits.items():
            if audit_data.get('score') is not None:
                if audit_data['score'] == 1:
                    passed_audits.append(audit_id)
                else:
                    failed_audits.append(audit_id)
                    
                    if audit_data.get('details') and audit_data['details'].get('type') == 'opportunity':
                        opportunities.append({
                            'audit': audit_id,
                            'title': audit_data.get('title', ''),
                            'description': audit_data.get('description', ''),
                            'score': audit_data.get('score', 0),
                            'potential_savings': audit_data.get('details', {}).get('overallSavingsMs', 0)
                        })
                    else:
                        issues.append({
                            'audit': audit_id,
                            'title': audit_data.get('title', ''),
                            'description': audit_data.get('description', ''),
                            'score': audit_data.get('score', 0)
                        })
        
        return {
            'performance_score': performance_score,
            'accessibility_score': accessibility_score,
            'seo_score': seo_score,
            'best_practices_score': best_practices_score,
            'issues': issues,
            'opportunities': opportunities,
            'passed_audits': passed_audits,
            'failed_audits': failed_audits
        }
    
    async def _run_technical_seo_audit(self, url: str) -> Dict[str, Any]:
        """Run technical SEO audit"""
        issues = []
        opportunities = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        issues.append({
                            'type': 'accessibility',
                            'message': f'Page returns {response.status} status code',
                            'severity': 'high'
                        })
                        return {'issues': issues, 'opportunities': opportunities}
                    
                    html_content = await response.text()
                    headers = response.headers
                    
                    # Analyze response headers
                    header_issues = self._analyze_response_headers(headers)
                    issues.extend(header_issues)
                    
                    # Analyze HTML content
                    content_issues, content_opportunities = self._analyze_html_content(html_content, url)
                    issues.extend(content_issues)
                    opportunities.extend(content_opportunities)
                    
                    # Check robots.txt
                    robots_issues = await self._check_robots_txt(session, url)
                    issues.extend(robots_issues)
                    
                    # Check sitemap.xml
                    sitemap_issues = await self._check_sitemap_xml(session, url)
                    issues.extend(sitemap_issues)
                    
        except Exception as e:
            issues.append({
                'type': 'technical',
                'message': f'Technical audit failed: {str(e)}',
                'severity': 'medium'
            })
        
        return {'issues': issues, 'opportunities': opportunities}
    
    def _analyze_response_headers(self, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        """Analyze HTTP response headers for SEO issues"""
        issues = []
        
        # Check for security headers
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Strict-Transport-Security'
        ]
        
        missing_headers = [header for header in security_headers if header not in headers]
        if missing_headers:
            issues.append({
                'type': 'security',
                'message': f'Missing security headers: {", ".join(missing_headers)}',
                'severity': 'medium'
            })
        
        # Check compression
        if 'Content-Encoding' not in headers or 'gzip' not in headers.get('Content-Encoding', ''):
            issues.append({
                'type': 'performance',
                'message': 'Response is not compressed with gzip',
                'severity': 'medium'
            })
        
        # Check caching headers
        if 'Cache-Control' not in headers and 'Expires' not in headers:
            issues.append({
                'type': 'performance',
                'message': 'No caching headers found',
                'severity': 'low'
            })
        
        return issues
    
    def _analyze_html_content(self, html_content: str, url: str) -> Tuple[List[Dict], List[Dict]]:
        """Analyze HTML content for SEO issues"""
        issues = []
        opportunities = []
        
        # Check for basic SEO elements
        if '<title>' not in html_content:
            issues.append({
                'type': 'seo',
                'message': 'Missing title tag',
                'severity': 'high'
            })
        
        if 'meta name="description"' not in html_content:
            issues.append({
                'type': 'seo',
                'message': 'Missing meta description',
                'severity': 'high'
            })
        
        # Check for heading structure
        h1_count = html_content.count('<h1')
        if h1_count == 0:
            issues.append({
                'type': 'seo',
                'message': 'Missing H1 tag',
                'severity': 'high'
            })
        elif h1_count > 1:
            issues.append({
                'type': 'seo',
                'message': 'Multiple H1 tags found',
                'severity': 'medium'
            })
        
        # Check for images without alt text
        img_without_alt = re.findall(r'<img(?![^>]*alt=)', html_content)
        if img_without_alt:
            issues.append({
                'type': 'accessibility',
                'message': f'{len(img_without_alt)} images missing alt text',
                'severity': 'medium'
            })
        
        # Check for schema markup opportunities
        if 'application/ld+json' not in html_content:
            opportunities.append({
                'type': 'schema',
                'message': 'Add structured data markup for better search visibility',
                'potential_impact': 'medium'
            })
        
        return issues, opportunities
    
    async def _check_robots_txt(self, session: aiohttp.ClientSession, base_url: str) -> List[Dict[str, Any]]:
        """Check robots.txt file"""
        issues = []
        
        try:
            robots_url = urljoin(base_url, '/robots.txt')
            async with session.get(robots_url) as response:
                if response.status == 404:
                    issues.append({
                        'type': 'technical',
                        'message': 'robots.txt file not found',
                        'severity': 'low'
                    })
                elif response.status == 200:
                    robots_content = await response.text()
                    if 'Sitemap:' not in robots_content:
                        issues.append({
                            'type': 'technical',
                            'message': 'robots.txt does not reference sitemap',
                            'severity': 'low'
                        })
        except Exception:
            pass  # robots.txt check is not critical
        
        return issues
    
    async def _check_sitemap_xml(self, session: aiohttp.ClientSession, base_url: str) -> List[Dict[str, Any]]:
        """Check sitemap.xml file"""
        issues = []
        
        try:
            sitemap_url = urljoin(base_url, '/sitemap.xml')
            async with session.get(sitemap_url) as response:
                if response.status == 404:
                    issues.append({
                        'type': 'technical',
                        'message': 'sitemap.xml file not found',
                        'severity': 'medium'
                    })
                elif response.status == 200:
                    try:
                        sitemap_content = await response.text()
                        ET.fromstring(sitemap_content)  # Validate XML
                    except ET.ParseError:
                        issues.append({
                            'type': 'technical',
                            'message': 'sitemap.xml contains invalid XML',
                            'severity': 'medium'
                        })
        except Exception:
            pass  # sitemap.xml check is not critical
        
        return issues
    
    async def _run_content_audit(self, url: str) -> Dict[str, Any]:
        """Run content-focused SEO audit"""
        issues = []
        opportunities = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        
                        # Extract text content
                        text_content = re.sub(r'<[^>]+>', ' ', html_content)
                        text_content = re.sub(r'\s+', ' ', text_content).strip()
                        
                        # Analyze content length
                        word_count = len(text_content.split())
                        if word_count < 300:
                            issues.append({
                                'type': 'content',
                                'message': f'Content is too short ({word_count} words). Aim for 300+ words',
                                'severity': 'medium'
                            })
                        
                        # Analyze readability
                        readability_score = self._calculate_readability(text_content)
                        if readability_score < 60:
                            opportunities.append({
                                'type': 'content',
                                'message': f'Content readability can be improved (score: {readability_score:.1f})',
                                'potential_impact': 'medium'
                            })
                        
                        # Check for internal linking opportunities
                        internal_links = len(re.findall(r'<a[^>]+href=["\'][^"\']*' + urlparse(url).netloc, html_content))
                        if internal_links < 3:
                            opportunities.append({
                                'type': 'content',
                                'message': 'Add more internal links to improve site navigation',
                                'potential_impact': 'low'
                            })
                        
        except Exception as e:
            issues.append({
                'type': 'content',
                'message': f'Content audit failed: {str(e)}',
                'severity': 'low'
            })
        
        return {'issues': issues, 'opportunities': opportunities}
    
    def _calculate_readability(self, text: str) -> float:
        """Calculate Flesch Reading Ease score"""
        if not text.strip():
            return 0
        
        # Count sentences, words, and syllables
        sentences = len(re.findall(r'[.!?]+', text))
        if sentences == 0:
            sentences = 1
        
        words = len(text.split())
        if words == 0:
            return 0
        
        # Simple syllable counting (approximation)
        syllables = sum(max(1, len(re.findall(r'[aeiouAEIOU]', word))) for word in text.split())
        
        # Flesch Reading Ease formula
        score = 206.835 - (1.015 * (words / sentences)) - (84.6 * (syllables / words))
        return max(0, min(100, score))
    
    def _calculate_overall_score(self, lighthouse_result: Dict, technical_result: Dict, content_result: Dict) -> float:
        """Calculate overall SEO score"""
        scores = []
        
        # Lighthouse scores (weighted)
        if isinstance(lighthouse_result, dict):
            if 'performance_score' in lighthouse_result:
                scores.append(lighthouse_result['performance_score'] * 0.3)
            if 'seo_score' in lighthouse_result:
                scores.append(lighthouse_result['seo_score'] * 0.4)
            if 'accessibility_score' in lighthouse_result:
                scores.append(lighthouse_result['accessibility_score'] * 0.2)
            if 'best_practices_score' in lighthouse_result:
                scores.append(lighthouse_result['best_practices_score'] * 0.1)
        
        # Technical audit penalty
        if isinstance(technical_result, dict):
            high_severity_issues = len([i for i in technical_result.get('issues', []) if i.get('severity') == 'high'])
            medium_severity_issues = len([i for i in technical_result.get('issues', []) if i.get('severity') == 'medium'])
            technical_penalty = (high_severity_issues * 10) + (medium_severity_issues * 5)
            scores = [max(0, score - technical_penalty) for score in scores]
        
        # Content audit bonus/penalty
        if isinstance(content_result, dict):
            content_issues = len(content_result.get('issues', []))
            content_penalty = content_issues * 3
            scores = [max(0, score - content_penalty) for score in scores]
        
        return sum(scores) / len(scores) if scores else 0
    
    async def analyze_competitors(self, keywords: List[str], limit: int = 5) -> List[CompetitorSEOData]:
        """Analyze competitor SEO for given keywords"""
        competitors = []
        
        # This would integrate with search APIs to find competitors
        # For now, returning mock data
        mock_competitors = [
            {
                'domain': 'competitor1.com',
                'title': 'Premium Products - Competitor 1',
                'description': 'Leading provider of premium products with excellent quality.',
                'keywords': keywords[:5],
                'h1_tags': ['Premium Products', 'Quality Assured'],
                'schema_markup': {'@type': 'Product'},
                'page_speed': 85.0,
                'mobile_friendly': True,
                'ssl_enabled': True
            }
        ]
        
        for comp_data in mock_competitors[:limit]:
            competitors.append(CompetitorSEOData(**comp_data))
        
        return competitors


class SEOContentOptimizer:
    """AI-powered SEO content optimization"""
    
    def __init__(self, tenant):
        self.tenant = tenant
    
    async def optimize_content_for_keywords(self, content: str, target_keywords: List[str]) -> Dict[str, Any]:
        """Optimize content for target keywords using NLP"""
        
        # Analyze current keyword density
        current_density = self._analyze_keyword_density(content, target_keywords)
        
        # Generate optimization suggestions
        suggestions = []
        
        for keyword in target_keywords:
            current_count = current_density.get(keyword, 0)
            optimal_density = self._calculate_optimal_density(len(content.split()), keyword)
            
            if current_count < optimal_density['min_count']:
                suggestions.append({
                    'type': 'keyword_density',
                    'keyword': keyword,
                    'current_count': current_count,
                    'recommended_count': optimal_density['target_count'],
                    'message': f'Consider adding "{keyword}" {optimal_density["target_count"] - current_count} more times'
                })
            elif current_count > optimal_density['max_count']:
                suggestions.append({
                    'type': 'keyword_density',
                    'keyword': keyword,
                    'current_count': current_count,
                    'recommended_count': optimal_density['target_count'],
                    'message': f'Consider reducing "{keyword}" usage by {current_count - optimal_density["target_count"]} times'
                })
        
        # Analyze content structure
        structure_suggestions = self._analyze_content_structure(content)
        suggestions.extend(structure_suggestions)
        
        # Generate semantic keyword suggestions
        semantic_keywords = self._generate_semantic_keywords(target_keywords)
        if semantic_keywords:
            suggestions.append({
                'type': 'semantic_keywords',
                'keywords': semantic_keywords,
                'message': f'Consider adding these related terms: {", ".join(semantic_keywords)}'
            })
        
        return {
            'current_keyword_density': current_density,
            'optimization_suggestions': suggestions,
            'readability_score': self._calculate_readability_score(content),
            'content_score': self._calculate_content_score(content, target_keywords)
        }
    
    def _analyze_keyword_density(self, content: str, keywords: List[str]) -> Dict[str, float]:
        """Analyze keyword density in content"""
        content_lower = content.lower()
        word_count = len(content.split())
        density = {}
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            count = content_lower.count(keyword_lower)
            density[keyword] = (count / word_count) * 100 if word_count > 0 else 0
        
        return density
    
    def _calculate_optimal_density(self, word_count: int, keyword: str) -> Dict[str, int]:
        """Calculate optimal keyword density"""
        # Target density: 1-3% for primary keywords
        target_density = 0.02  # 2%
        min_density = 0.01     # 1%
        max_density = 0.03     # 3%
        
        return {
            'target_count': int(word_count * target_density),
            'min_count': int(word_count * min_density),
            'max_count': int(word_count * max_density)
        }
    
    def _analyze_content_structure(self, content: str) -> List[Dict[str, Any]]:
        """Analyze content structure for SEO"""
        suggestions = []
        
        # Check paragraph length
        paragraphs = content.split('\n\n')
        long_paragraphs = [p for p in paragraphs if len(p.split()) > 150]
        
        if long_paragraphs:
            suggestions.append({
                'type': 'structure',
                'message': f'{len(long_paragraphs)} paragraphs are too long. Break them into shorter sections.',
                'severity': 'medium'
            })
        
        # Check for subheadings
        if not re.search(r'#{2,6}|\<h[2-6]', content):
            suggestions.append({
                'type': 'structure',
                'message': 'Add subheadings (H2, H3) to improve content structure',
                'severity': 'medium'
            })
        
        # Check for bullet points or lists
        if not re.search(r'[-*+]\s|<[uo]l>|\d+\.\s', content):
            suggestions.append({
                'type': 'structure',
                'message': 'Consider adding bullet points or numbered lists for better readability',
                'severity': 'low'
            })
        
        return suggestions
    
    def _generate_semantic_keywords(self, keywords: List[str]) -> List[str]:
        """Generate semantic keywords (LSI keywords)"""
        # This would use NLP models to generate related terms
        # For now, return simple variations
        semantic_keywords = []
        
        for keyword in keywords:
            # Add plural/singular variations
            if keyword.endswith('s'):
                semantic_keywords.append(keyword[:-1])
            else:
                semantic_keywords.append(keyword + 's')
        
        return semantic_keywords[:5]
    
    def _calculate_readability_score(self, content: str) -> float:
        """Calculate content readability score"""
        if not content.strip():
            return 0
        
        sentences = len(re.findall(r'[.!?]+', content))
        if sentences == 0:
            sentences = 1
        
        words = len(content.split())
        if words == 0:
            return 0
        
        # Simplified readability calculation
        avg_sentence_length = words / sentences
        
        # Penalize very long sentences
        if avg_sentence_length > 25:
            return max(0, 100 - (avg_sentence_length - 25) * 2)
        else:
            return min(100, 80 + (25 - avg_sentence_length))
    
    def _calculate_content_score(self, content: str, target_keywords: List[str]) -> float:
        """Calculate overall content SEO score"""
        score = 100
        
        # Word count penalty/bonus
        word_count = len(content.split())
        if word_count < 300:
            score -= 20
        elif word_count > 2000:
            score -= 10
        elif 500 <= word_count <= 1500:
            score += 10
        
        # Keyword optimization score
        keyword_density = self._analyze_keyword_density(content, target_keywords)
        for keyword, density in keyword_density.items():
            if 1 <= density <= 3:
                score += 5
            elif density > 5:
                score -= 10
        
        # Readability score impact
        readability = self._calculate_readability_score(content)
        if readability < 60:
            score -= 15
        elif readability > 80:
            score += 5
        
        return max(0, min(100, score))