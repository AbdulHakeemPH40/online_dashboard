"""
AI-Powered Pricing Agent for Pasons & Talabat Platforms
Uses OpenAI GPT models for intelligent pricing recommendations

Features:
- Dynamic pricing based on market conditions
- Competitive analysis
- Seasonal adjustments
- Demand forecasting
- Smart margin optimization

Usage:
    from integration.ai_agentic import AIPricingAssistant
    
    agent = AIPricingAssistant(api_key=settings.OPENAI_API_KEY)
    recommendation = agent.get_pricing_recommendation(
        item_code='9900186',
        base_price=4.49,
        category='Groceries',
        platform='talabat'
    )
"""

import json
import logging
import time
from decimal import Decimal
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AIPricingAssistant:
    """
    AI-powered pricing recommendations using OpenAI GPT models
    
    Integrates with PricingCalculator for final price validation
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        """
        Initialize AI Pricing Assistant
        
        Args:
            api_key: OpenAI API key
            model: GPT model to use (default: gpt-4)
        """
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
            self.model = model
            self.enabled = True
            self.max_retries = 3
            self.retry_delay = 1  # seconds
        except ImportError:
            logger.warning("OpenAI library not installed. AI pricing disabled.")
            self.enabled = False
            self.max_retries = 0
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.enabled = False
            self.max_retries = 0
    
    def get_pricing_recommendation(
        self,
        item_code: str,
        base_price: float,
        category: str,
        platform: str,
        market_data: Optional[Dict] = None,
        competitors: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Get AI-powered pricing recommendation
        
        Args:
            item_code: Item code
            base_price: Base price from calculation
            category: Product category
            platform: 'pasons' or 'talabat'
            market_data: Optional market insights
            competitors: Optional competitor pricing data
            
        Returns:
            {
                'recommended_price': float,
                'margin_percentage': float,
                'reasoning': str,
                'confidence': float (0-1),
                'factors': list,
                'ai_enabled': bool
            }
        """
        if not self.enabled:
            return self._fallback_recommendation(base_price, platform, item_code)
        
        # Try to get AI recommendation with retry logic
        for attempt in range(self.max_retries):
            try:
                # Prepare context
                context = self._build_pricing_context(
                    item_code=item_code,
                    base_price=base_price,
                    category=category,
                    platform=platform,
                    market_data=market_data,
                    competitors=competitors
                )
                
                # Generate AI recommendation
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self._get_system_prompt()
                        },
                        {
                            "role": "user",
                            "content": json.dumps(context)
                        }
                    ],
                    temperature=0.7
                    # Removed response_format for broader model compatibility
                )
                
                # Parse response - handle both JSON and text responses
                response_text = response.choices[0].message.content
                
                try:
                    # Try to parse as JSON first
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    # If not JSON, extract key information from text
                    logger.warning(f"AI response not in JSON format, parsing text: {response_text[:100]}...")
                    result = self._parse_text_response(response_text, base_price, platform, item_code)
                
                result['ai_enabled'] = True
                
                # Validate and apply smart rounding
                result = self._validate_recommendation(result, base_price, platform)
                
                logger.info(f"AI pricing recommendation for {item_code}: {result}")
                return result
            
            except Exception as e:
                # Specific error handling
                try:
                    from openai import RateLimitError, APIConnectionError, APIStatusError, AuthenticationError
                    
                    if isinstance(e, RateLimitError):
                        # Rate limit - retry with exponential backoff
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (2 ** attempt)
                            logger.warning(f"OpenAI rate limit (attempt {attempt + 1}/{self.max_retries}), retrying in {wait_time}s: {e}")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"OpenAI rate limit exceeded after {self.max_retries} retries")
                            return self._fallback_recommendation(base_price, platform, item_code)
                    
                    elif isinstance(e, APIConnectionError):
                        # Connection error - retry
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (2 ** attempt)
                            logger.warning(f"OpenAI connection error (attempt {attempt + 1}/{self.max_retries}), retrying in {wait_time}s: {e}")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"OpenAI connection failed after {self.max_retries} retries")
                            return self._fallback_recommendation(base_price, platform, item_code)
                    
                    elif isinstance(e, AuthenticationError):
                        # Authentication error - no point retrying
                        logger.error(f"OpenAI authentication failed (invalid API key or insufficient permissions): {e}")
                        return self._fallback_recommendation(base_price, platform, item_code)
                    
                    elif isinstance(e, APIStatusError):
                        # API status error (5xx errors, etc)
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (2 ** attempt)
                            logger.warning(f"OpenAI API error (attempt {attempt + 1}/{self.max_retries}), retrying in {wait_time}s: {e}")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"OpenAI API error after {self.max_retries} retries")
                            return self._fallback_recommendation(base_price, platform, item_code)
                    
                    else:
                        # Unexpected error
                        logger.error(f"Unexpected AI error for {item_code}: {type(e).__name__}: {e}")
                        return self._fallback_recommendation(base_price, platform, item_code)
                
                except ImportError:
                    # OpenAI exceptions not available - fall back to generic handling
                    logger.error(f"AI pricing failed for {item_code}: {type(e).__name__}: {e}")
                    return self._fallback_recommendation(base_price, platform, item_code)
    
    def _build_pricing_context(
        self,
        item_code: str,
        base_price: float,
        category: str,
        platform: str,
        market_data: Optional[Dict],
        competitors: Optional[List[Dict]]
    ) -> Dict:
        """
        Build context for AI pricing decision
        """
        return {
            "item_code": item_code,
            "base_price": base_price,
            "category": category,
            "platform": platform,
            "currency": "AED",
            "market": "UAE",
            "date": datetime.now().isoformat(),
            "market_data": market_data or {},
            "competitors": competitors or [],
            "constraints": {
                "smart_rounding_targets": [0.00, 0.25, 0.49, 0.75, 0.99],
                "talabat_margins": {
                    "wrap_9900": 17.0,      # Wrap items (9900xxx) = 17%
                    "regular_10000": 15.0,   # Regular items (10000xxx) = 15%
                    "custom": "User can set ANY % via rules_update_price.html"
                },
                "max_margin_talabat": 30.0,
                "platform_rules": self._get_platform_rules(platform)
            }
        }
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt for AI pricing
        """
        return """You are an expert pricing strategist for UAE retail market specializing in Pasons and Talabat platforms.

Your task is to recommend optimal selling prices considering:

1. **Smart Rounding Rules**: Prices must end with .00, .25, .49, .75, or .99
2. **Platform Margins**:
   - Pasons: No additional margin (base price from ERP)
   - Talabat: 
     * Wrap items (9900xxx): 17% margin
     * Regular items (10000xxx): 15% margin
     * Custom margin: User can set ANY % via rules_update_price.html
3. **Psychological Pricing**: Use .49 and .99 endings for consumer appeal
4. **Market Competitiveness**: Consider competitor pricing if provided
5. **Category Dynamics**: Adjust for category-specific factors
6. **Seasonal Factors**: Account for demand fluctuations

Response Format (JSON):
{
    "recommended_price": <float>,
    "margin_percentage": <float>,
    "reasoning": "<brief explanation>",
    "confidence": <0.0-1.0>,
    "factors": ["factor1", "factor2", ...]
}

Always ensure recommended_price uses smart rounding targets.
For Talabat, use 17% for wrap items (9900xxx) and 15% for regular items (10000xxx).
Provide clear, actionable reasoning."""
    
    def _get_platform_rules(self, platform: str) -> Dict:
        """
        Get platform-specific rules
        """
        if platform.lower() == 'pasons':
            return {
                "margin_allowed": False,
                "smart_rounding": "optional",
                "rounding_mode": "nearest",
                "description": "Pasons uses ERP prices with optional smart rounding"
            }
        elif platform.lower() == 'talabat':
            return {
                "margin_allowed": True,
                "margins": {
                    "wrap_9900": 17.0,
                    "regular_10000": 15.0
                },
                "smart_rounding": "mandatory",
                "rounding_mode": "ceiling",
                "description": "Talabat: 17% for wrap (9900xxx), 15% for regular (10000xxx), custom margin via rules_update_price.html"
            }
        else:
            return {}
    
    def _parse_text_response(self, text: str, base_price: float, platform: str, item_code: str = None) -> Dict:
        """
        Parse AI response when it's not in JSON format
        Extracts price and reasoning from text
        
        Margin logic matches models.py:
        - Wrap items (9900xxx): 17% for Talabat
        - Regular items: 15% for Talabat
        - Pasons: 0%
        """
        import re
        
        # Try to find price in text
        price_match = re.search(r'(\d+\.\d+)\s*AED', text)
        if price_match:
            recommended_price = float(price_match.group(1))
        else:
            # Fallback to base price with margin
            from .utils import PricingCalculator
            base_decimal = Decimal(str(base_price))
            if platform.lower() == 'talabat':
                # Pass item_code for proper margin detection (17% wrap, 15% regular)
                recommended_price, _ = PricingCalculator.calculate_talabat_price(
                    base_decimal, 
                    margin_percentage=None, 
                    item_code=item_code
                )
            else:
                recommended_price = PricingCalculator.smart_round(base_decimal)
            recommended_price = float(recommended_price)
        
        # Get default margin based on item type
        if platform.lower() == 'talabat':
            from .utils import PricingCalculator
            default_margin = float(PricingCalculator.get_default_talabat_margin(item_code or ''))
        else:
            default_margin = 0.0
        
        # Extract margin if mentioned in text, otherwise use default
        margin_match = re.search(r'(\d+)\s*%', text)
        margin = float(margin_match.group(1)) if margin_match else default_margin
        
        return {
            'recommended_price': recommended_price,
            'margin_percentage': margin,
            'reasoning': text[:200] if len(text) > 200 else text,
            'confidence': 0.6,
            'factors': ['ai_text_parsing']
        }
    
    def _validate_recommendation(
        self,
        recommendation: Dict,
        base_price: float,
        platform: str
    ) -> Dict:
        """
        Validate AI recommendation and apply smart rounding
        """
        from .utils import PricingCalculator
        
        # Ensure price uses smart rounding
        recommended = Decimal(str(recommendation.get('recommended_price', base_price)))
        
        if platform.lower() == 'talabat':
            # Apply smart ceiling for Talabat
            validated_price = PricingCalculator.smart_ceiling(recommended)
        else:
            # Apply smart rounding for Pasons
            validated_price = PricingCalculator.smart_round(recommended, mode='nearest')
        
        # Update recommendation
        recommendation['recommended_price'] = float(validated_price)
        recommendation['original_ai_price'] = float(recommended)
        
        # Ensure confidence is between 0 and 1
        confidence = recommendation.get('confidence', 0.7)
        recommendation['confidence'] = max(0.0, min(1.0, confidence))
        
        return recommendation
    
    def _fallback_recommendation(self, base_price: float, platform: str, item_code: str = None) -> Dict:
        """
        Fallback recommendation when AI is unavailable
        
        Margin logic matches models.py effective_talabat_margin:
        - Wrap items (9900xxx): 17% for Talabat
        - Regular items (100xxx): 15% for Talabat
        - Pasons: 0%
        """
        from .utils import PricingCalculator
        
        base_decimal = Decimal(str(base_price))
        
        if platform.lower() == 'talabat':
            # Get margin based on item type (17% for wrap, 15% for regular)
            margin_pct = float(PricingCalculator.get_default_talabat_margin(item_code or ''))
            # Calculate price with proper margin
            final_price, margin_amt = PricingCalculator.calculate_talabat_price(
                base_decimal, 
                margin_percentage=None,
                item_code=item_code
            )
        else:
            # Pasons: smart rounding only, no margin
            final_price = PricingCalculator.smart_round(base_decimal)
            margin_pct = 0.0
        
        return {
            'recommended_price': float(final_price),
            'margin_percentage': margin_pct,
            'reasoning': 'Standard platform rules applied (AI unavailable)',
            'confidence': 0.5,
            'factors': ['platform_defaults', 'smart_rounding'],
            'ai_enabled': False
        }
    
    def bulk_pricing_recommendations(
        self,
        items: List[Dict],
        platform: str
    ) -> List[Dict]:
        """
        Get pricing recommendations for multiple items
        
        Args:
            items: List of item dictionaries with keys:
                   item_code, base_price, category
            platform: Target platform
            
        Returns:
            List of recommendations with item_code included
        """
        recommendations = []
        
        for item in items:
            try:
                rec = self.get_pricing_recommendation(
                    item_code=item.get('item_code'),
                    base_price=item.get('base_price'),
                    category=item.get('category', 'General'),
                    platform=platform,
                    market_data=item.get('market_data'),
                    competitors=item.get('competitors')
                )
                rec['item_code'] = item.get('item_code')
                recommendations.append(rec)
            except Exception as e:
                logger.error(f"Failed to get recommendation for {item.get('item_code')}: {e}")
                from .utils import PricingCalculator
                recommendations.append({
                    'item_code': item.get('item_code'),
                    'recommended_price': item.get('base_price'),
                    'margin_percentage': float(PricingCalculator.get_default_talabat_margin(item.get('item_code', ''))) if platform == 'talabat' else 0.0,
                    'reasoning': f'Error: {str(e)}',
                    'confidence': 0.0,
                    'factors': ['error'],
                    'ai_enabled': False
                })
        
        return recommendations


class PricingDataAnalyzer:
    """
    Analyze pricing data using pandas for insights and optimization
    """
    
    def __init__(self):
        """
        Initialize pricing data analyzer
        """
        try:
            import pandas as pd
            import numpy as np
            self.pd = pd
            self.np = np
            self.enabled = True
        except ImportError:
            logger.warning("pandas/numpy not installed. Data analysis disabled.")
            self.enabled = False
    
    def analyze_pricing_distribution(self, prices: List[float]) -> Dict:
        """
        Analyze price distribution
        
        Args:
            prices: List of prices
            
        Returns:
            Statistical analysis
        """
        if not self.enabled or not prices:
            return {}
        
        df = self.pd.DataFrame({'price': prices})
        
        return {
            'count': len(prices),
            'mean': float(df['price'].mean()),
            'median': float(df['price'].median()),
            'std': float(df['price'].std()),
            'min': float(df['price'].min()),
            'max': float(df['price'].max()),
            'percentiles': {
                '25': float(df['price'].quantile(0.25)),
                '50': float(df['price'].quantile(0.50)),
                '75': float(df['price'].quantile(0.75)),
                '90': float(df['price'].quantile(0.90))
            }
        }
    
    def detect_pricing_anomalies(
        self,
        items_df,
        threshold_std: float = 2.0
    ) -> List[Dict]:
        """
        Detect pricing anomalies using statistical analysis
        
        Args:
            items_df: DataFrame with columns: item_code, price, category
            threshold_std: Standard deviation threshold
            
        Returns:
            List of anomalous items
        """
        if not self.enabled:
            return []
        
        anomalies = []
        
        for category in items_df['category'].unique():
            cat_items = items_df[items_df['category'] == category]
            mean = cat_items['price'].mean()
            std = cat_items['price'].std()
            
            # Find outliers
            outliers = cat_items[
                (cat_items['price'] < mean - threshold_std * std) |
                (cat_items['price'] > mean + threshold_std * std)
            ]
            
            for _, item in outliers.iterrows():
                anomalies.append({
                    'item_code': item['item_code'],
                    'price': float(item['price']),
                    'category': category,
                    'category_mean': float(mean),
                    'deviation': float(abs(item['price'] - mean) / std),
                    'reason': 'statistical_outlier'
                })
        
        return anomalies
