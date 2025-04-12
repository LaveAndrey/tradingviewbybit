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
        self._coin_cache = {}
        self.base_url = "https://pro-api.coinmarketcap.com/v2"  # Обновлено до v2 API

    async def _get_all_coins(self) -> Dict:
        """Получает и кэширует список всех монет"""
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
        clean_symbol = self.extract_symbol(symbol).upper()  # Всегда используем верхний регистр

        for attempt in range(self.retries):
            try:
                url = f"{self.base_url}/cryptocurrency/quotes/latest"
                headers = {
                    'Accepts': 'application/json',
                    'X-CMC_PRO_API_KEY': self.api_key
                }
                params = {
                    'symbol': clean_symbol,
                    'convert': 'USD'
                }

                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                # Новый способ обработки ответа для v2 API
                if not data.get('data'):
                    logger.error(f"Нет данных для {clean_symbol} в ответе API")
                    return None, None

                # Получаем первый элемент из данных
                coin_data = next(iter(data['data'].values()))
                quote = coin_data['quote']['USD']

                market_cap = quote.get('market_cap')
                volume = quote.get('volume_24h')

                if market_cap is None or volume is None:
                    logger.warning(f"Отсутствуют данные для {clean_symbol}, попытка {attempt + 1}")
                    await asyncio.sleep(self.delay)
                    continue

                return market_cap, volume

            except RequestException as e:
                logger.error(f"Ошибка запроса (попытка {attempt + 1}): {e}")
                if attempt < self.retries - 1:
                    await asyncio.sleep(self.delay)
                continue
            except Exception as e:
                logger.error(f"Неожиданная ошибка при обработке данных: {str(e)}", exc_info=True)
                return None, None

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
        return f"{value:,.2f}" if value >= 1000 else f"{value:.2f}"