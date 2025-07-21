HOW STRATEGIES REQUEST / SUBSCRIBE FOR MARKET-DATA

Let's design, how strategies should / should not request for market data,
they need to get.

First principle:
- Strategy should never know, if any market-data (like bar, ticks, ..) are historical or live. This allow to run backtest and live-trading in the same way.

2nd principle
- The same strategy can be run on various market data
  - like on EUR/USD vs. GBP/USD without any change
  - This show, that any strategy cannot required fixed / static market data, but it needs to be configurable, what data it will request (probably in constructor or some custom StrategyConfig)
- It is completely OK, if strategy can for example choose random market data (or by any custom logic) and trade them, what shows that strategy cannot request some static/fixed set of market data

This results in situation, that:
- Strategy decides, what market-data it needs and this can be based on:
  - input configuration of the Strategy (in constructor params or some specific StrategyConfig)
  - or some internal logic (like Stock screening / random seleection / any other custom logic)

3rd principle:
- Strategy needs to know / decide, how many data historical data it needs to initialize itself and its indicators
- Strategy decides, if it wants / needs to subscribe to live data

Both of these decisions can be based on the strategy configuration.

In practice, there are only 2 main scenarios:
a) BackTesting mode:
    - Strategy knows:
        - what historical market data it needs and in which period (from-until)
b) LiveTrading mode:
    - Strategy knows:
        - what live data it needs to subscribe to
        - and how many historical data it needs to initialize itself
        - + strategy needs to make sure, there are no data gaps between historical + live data
    - Technically it is possible (for some strategies), that no historical data are needed like:
        - in strategies, that do some stock-screening and don't need to know historical data
        - in strategies, that wait for some specific condition / time and don't need to know historical data

Here is the pattern we can see:
Strategy needs to know (or be configured that way) if it:
- needs live-data or not (for specified instruments)
- if it needs historical data or not (for specified instrument) and this can be in 2 forms
  - in BackTesting mode:
      - Strategy defines:
        - one or more instruments
        - and to each instrument is needs to define 2 datetimes: $from + $until, so we know what range of historical data should be fed into the strategy
          - The point is, that $until is still in the history (before current time)
  - in LiveTrading mode:
    - Strategy defines:
      - one or more instrument
      - but only $from datetime is needed, as $until is automatically clear, that the historical data have to go until now
        - the goal is to achieve, the live-data directly connect (without gaps) to the historical data

This shows the requirements for Strategy(ies) and how they should be designed,
so they can have single interface / protocol, that could meet requirements
of both scenarios - BackTesting mode + LiveTrading mode.

There should be only one Strategy, that could have means (functionality) to operate in both scenarios.

4th principle"
The point it, that the Strategy does not have to know the market data it
needs at startup. That means, it should be able to subscribe to any market data (historical or live)
anytime during its lifetime.

Examples of strategies:
- Strategy 1:
  - asks for historical data:
    - 1-minute bars
    - instrument EUR/USD forex
    - from 1.1.2001 - until 31.12.2001
  - This strategy does only backtesting
- Strategy 2:
  - wants to trade live with:
    - 1-minute bars
    - instrument EUR/USD forex
  - but needs to initialized with:
    - 30 days of historical data first
- Strategy 3:
  - wants to trade live with:
    - 1-minute bars
    - instrument EUR/USD forex
  - and does not need any historical data, because it's logic is just to wait until 14:30 time and make a trade at that time = this strategy just need current time to know, when it should submit order
- Strategy 4:
  - wants to trade live with:
    - 1-minute bars of instrument EUR/USD forex
    - 1-minute bars of instrument GBP/USD forex
  - but needs to initialized with:
    - 30 days of historical data first (for both instruments)
- Strategy 5:
  - Does not know, what it is goint to trade on startup
  - Strategy scans tweets on Twitter (X.com) and if it finds some signal for specific instrument, then:
    - it can ask to be initialized with 10 days of historical data + subscribe to live data
    - Strategy will be periodically doing some technical analysis and based on it, it can optionally makes some trades (submit orders)
  - This scenario is, that here can be long time, when strategy does not need any market data, but later it can ask for them:
    - it can ask for historical data - to be initialized
    - it can ask for live data to continue
  - Technically, it would be possible, that Strategy again can go back to the state, where it unsubscribes from data, resets its state and get back to the state, where it does not need market data anymore (it is just scanning tweets again)
    - This scenario show, that any Strategy should be able to be feeded by any historical / live data
      - and this could be reversible - like Strategy can unsubscribe to these data -> reset its state optionally -> and ask for any other data again (historical / live)


THIS IS OUR MAIN GOAL - DESIGN / ARCHITECTURE CHALLENGE:
Based on this description, we should identify the base / generic / universal functions,
that:
- Strategy should have
- TradingEngine should have
- what interface we need - like HistoricalDataProvider / LiveDataProvider, from which TradingEngine really gets these data and distributes them to individual Strategies vie MessageBus.
