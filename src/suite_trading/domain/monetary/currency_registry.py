from suite_trading.domain.monetary.currency import Currency, CurrencyType


# Fiat currencies
USD = Currency("USD", 2, "US Dollar", CurrencyType.FIAT)
EUR = Currency("EUR", 2, "Euro", CurrencyType.FIAT)
GBP = Currency("GBP", 2, "British Pound", CurrencyType.FIAT)
JPY = Currency("JPY", 0, "Japanese Yen", CurrencyType.FIAT)

# Crypto currencies
BTC = Currency("BTC", 8, "Bitcoin", CurrencyType.CRYPTO)
ETH = Currency("ETH", 18, "Ethereum", CurrencyType.CRYPTO)
USDT = Currency("USDT", 6, "Tether", CurrencyType.CRYPTO)

# Commodities
XAU = Currency("XAU", 4, "Gold", CurrencyType.COMMODITY)
XAG = Currency("XAG", 4, "Silver", CurrencyType.COMMODITY)

# Register all predefined currencies
Currency.register(USD, overwrite=True)
Currency.register(EUR, overwrite=True)
Currency.register(GBP, overwrite=True)
Currency.register(JPY, overwrite=True)
Currency.register(BTC, overwrite=True)
Currency.register(ETH, overwrite=True)
Currency.register(USDT, overwrite=True)
Currency.register(XAU, overwrite=True)
Currency.register(XAG, overwrite=True)
