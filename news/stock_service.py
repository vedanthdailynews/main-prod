"""
Stock market service for fetching live Indian stock market data.
"""
import yfinance as yf
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class StockMarketService:
    """Service to fetch live stock market data from NSE India."""
    
    # NIFTY indices with their Yahoo Finance symbols
    NIFTY_INDICES = {
        'NIFTY50': '^NSEI',              # NIFTY 50
        'NIFTY_BANK': '^NSEBANK',        # NIFTY Bank
        'NIFTY_IT': '^CNXIT',            # NIFTY IT
        'NIFTY_AUTO': '^CNXAUTO',        # NIFTY Auto
        'NIFTY_FIN_SERVICE': '^CNXFIN',  # NIFTY Financial Services
        'NIFTY_FMCG': '^CNXFMCG',        # NIFTY FMCG
        'NIFTY_PHARMA': '^CNXPHARMA',    # NIFTY Pharma
        'NIFTY_METAL': '^CNXMETAL',      # NIFTY Metal
        'NIFTY_REALTY': '^CNXREALTY',    # NIFTY Realty
        'NIFTY_ENERGY': '^CNXENERGY',    # NIFTY Energy
        'NIFTY_MEDIA': '^CNXMEDIA',      # NIFTY Media
        'NIFTY_INFRA': '^CNXINFRA',      # NIFTY Infrastructure
        'NIFTY_PSU_BANK': '^CNXPSUBANK', # NIFTY PSU Bank
        'NIFTY_PVT_BANK': '^CNXPVTBANK', # NIFTY Private Bank
        'NIFTY_MIDCAP': '^NSEMDCP50',    # NIFTY Midcap 100
        'NIFTY_SMLCAP': '^CNXSC',        # NIFTY Smallcap 100
    }
    
    @staticmethod
    def get_live_market_data() -> List[Dict]:
        """
        Fetch live market data for major NIFTY indices.
        
        Returns:
            List of dictionaries containing index data
        """
        market_data = []
        
        try:
            for index_name, symbol in StockMarketService.NIFTY_INDICES.items():
                try:
                    # Fetch ticker data
                    ticker = yf.Ticker(symbol)
                    
                    # Get current price and info
                    info = ticker.info
                    hist = ticker.history(period='1d')
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        previous_close = info.get('previousClose', info.get('regularMarketPreviousClose', 0))
                        
                        # Calculate change
                        if previous_close and previous_close > 0:
                            change = current_price - previous_close
                            change_percent = (change / previous_close) * 100
                        else:
                            change = 0
                            change_percent = 0
                        
                        # Format display name
                        name_map = {
                            'NIFTY50': 'NIFTY 50',
                            'NIFTY_BANK': 'NIFTY Bank',
                            'NIFTY_IT': 'NIFTY IT',
                            'NIFTY_AUTO': 'NIFTY Auto',
                            'NIFTY_FIN_SERVICE': 'NIFTY Financial Services',
                            'NIFTY_FMCG': 'NIFTY FMCG',
                            'NIFTY_PHARMA': 'NIFTY Pharma',
                            'NIFTY_METAL': 'NIFTY Metal',
                            'NIFTY_REALTY': 'NIFTY Realty',
                            'NIFTY_ENERGY': 'NIFTY Energy',
                            'NIFTY_MEDIA': 'NIFTY Media',
                            'NIFTY_INFRA': 'NIFTY Infrastructure',
                            'NIFTY_PSU_BANK': 'NIFTY PSU Bank',
                            'NIFTY_PVT_BANK': 'NIFTY Private Bank',
                            'NIFTY_MIDCAP': 'NIFTY Midcap 100',
                            'NIFTY_SMLCAP': 'NIFTY Smallcap 100',
                        }
                        display_name = name_map.get(index_name, index_name.replace('_', ' ').title())
                        
                        market_data.append({
                            'name': display_name,
                            'symbol': symbol,
                            'price': round(current_price, 2),
                            'change': round(change, 2),
                            'change_percent': round(change_percent, 2),
                            'direction': 'up' if change >= 0 else 'down',
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        logger.info(f"Fetched {display_name}: {current_price:.2f}")
                    
                except Exception as e:
                    logger.error(f"Error fetching {index_name}: {e}")
                    continue
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return []
    
    @staticmethod
    def get_index_data(symbol: str) -> Dict:
        """
        Get detailed data for a specific index.
        
        Args:
            symbol: Yahoo Finance symbol (e.g., '^NSEI')
            
        Returns:
            Dictionary with index details
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='5d')
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                previous_close = info.get('previousClose', 0)
                
                return {
                    'symbol': symbol,
                    'price': round(current_price, 2),
                    'previous_close': round(previous_close, 2),
                    'day_high': round(hist['High'].iloc[-1], 2),
                    'day_low': round(hist['Low'].iloc[-1], 2),
                    'volume': int(hist['Volume'].iloc[-1]),
                    'history': hist.to_dict('records')
                }
        
        except Exception as e:
            logger.error(f"Error fetching index data for {symbol}: {e}")
            return {}
