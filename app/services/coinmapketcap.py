import logging
from typing import Tuple, Optional, Dict
import asyncio
import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class CoinMarketCapService:
    def __init__(self, api_key: str, retries: int = 3, delay: float = 1.0):
        self.api_key = api_key
        self.retries = retries
        self.delay = delay
        self._coin_cache = {}  # Кэш для хранения данных о монетах
        self.base_url = "https://pro-api.coinmarketcap.com/v1"

    async def _get_all_coins(self) -> Dict:
        """Получает и кэширует список всех монет с их ID"""
        if not self._coin_cache:
            try:
                url = f"{self.base_url}/cryptocurrency/map"
                headers = {
                    'Accepts': 'application/json',
                    'X-CMC_PRO_API_KEY': self.api_key
                }

                response = requests.get(url, headers=headers)
                response.raise_for_status()

                data = response.json()
                coins = data.get('data', [])
                self._coin_cache = {coin['symbol'].lower(): coin for coin in coins}
                logger.info("Кэш монет успешно обновлен")
            except RequestException as e:
                logger.error(f"Ошибка получения списка монет: {e}")
                raise
        return self._coin_cache

    async def get_market_data(self, symbol: str) -> Tuple[Optional[float], Optional[float]]:
        """Получает рыночные данные (капитализацию и объем)"""
        try:
            coins = await self._get_all_coins()
            coin_data = coins.get(symbol.lower())
            if not coin_data:
                logger.warning(f"Монета {symbol} не найдена")
                return None, None

            for attempt in range(self.retries):
                try:
                    url = f"{self.base_url}/cryptocurrency/quotes/latest"
                    headers = {
                        'Accepts': 'application/json',
                        'X-CMC_PRO_API_KEY': self.api_key
                    }
                    params = {
                        'id': coin_data['id'],
                        'convert': 'USD'
                    }

                    response = requests.get(url, headers=headers, params=params)
                    response.raise_for_status()

                    data = response.json()
                    coin_info = data['data'][str(coin_data['id'])]
                    quote = coin_info['quote']['USD']

                    market_cap = quote.get('market_cap')
                    volume = quote.get('volume_24h')

                    return market_cap, volume
                except RequestException as e:
                    logger.error(f"Попытка {attempt + 1} не удалась: {e}")
                    if attempt < self.retries - 1:
                        await asyncio.sleep(self.delay)

            return None, None
        except Exception as e:
            logger.error(f"Ошибка в get_market_data: {e}")
            return None, None

    @staticmethod
    def extract_symbol(ticker: str) -> str:
        """Извлекает чистый символ из тикера"""
        ticker = ticker.upper()
        for suffix in ["USDT.P", "USDT", "PERP", "USD.P"]:
            if ticker.endswith(suffix):
                return ticker[:-len(suffix)]
        return ticker

    @staticmethod
    def format_number(value: Optional[float]) -> str:
        """Форматирует числа с разделителями"""
        if value is None:
            return "N/A"
        return f"{value:,.2f}" if isinstance(value, float) else f"{int(value):,}"