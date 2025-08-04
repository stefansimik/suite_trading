# PROBLEM

## Trading Strategy Data Problem: Getting Market Data in the Right Order

### ### What Kind of Problem This Is

This is a **timing problem** in trading software. We need to make sure that when a trading strategy gets market data (like stock prices), the data always comes in the right time order - from oldest to newest.

### ### The Main Problem

Right now, our trading strategies can ask for market data anytime they want using various methods. But this creates a big problem: **the data can arrive out of order**, which breaks how trading strategies are supposed to work.

### ### What Goes Wrong

#### **Safe Ways to Get Data (These Work Fine)**

**Getting Historical Data Once:**
- ✅ **Works well**: Strategy calls `get_historical_events()` once and gets all the data at the same time
- ✅ **No problems**: The data comes in the right order

**Getting Live Data:**
- ✅ **Works well**: Strategy calls `start_live_stream()` to get new data as it happens in real-time
- ✅ **Natural order**: Live data naturally comes in time order

#### **Dangerous Ways to Get Data (These Cause Problems)**

**Getting Historical Data Multiple Times:**
- ❌ **Big problem**: Strategy can call `stream_historical_events()` for EUR/USD data from January-March, then call it again for GBP/USD data from last year
- ❌ **Time confusion**: Strategy gets newer data first, then older data later
- ❌ **Makes no sense**: It's like going back in time, which breaks trading logic

**Getting Live Data with Historical Data Mixed In:**
- ❌ **Big problem**: Strategy calls `start_live_stream_with_history()` while already getting today's live data, then suddenly gets old data from last month
- ❌ **Time mess**: Strategy doesn't know what time it's supposed to be at
- ❌ **Confusing**: Strategy can't tell if it's looking at old or new information

**Getting Data for Multiple Instruments:**
- ❌ **Critical problem**: Strategy has to call `stream_historical_events()` separately for each instrument (EUR/USD, then GBP/USD, then USD/JPY)
- ❌ **Data arrives mixed up**: EUR/USD data from 9:00 AM might arrive after GBP/USD data from 9:15 AM
- ❌ **Wrong order**: Strategy gets confused about what happened when

### ### Why This Happens

#### **The Root Problems**

1. **No time rules**: Strategies can call any data method at any time
2. **No order checking**: System doesn't make sure data arrives in time order
3. **Mixed up data**: Historical and live data get mixed together randomly
4. **No time tracking**: Strategy doesn't know what time it's supposed to be at
5. **One instrument at a time**: `stream_historical_events()` can only handle one instrument per call
6. **No coordination**: When calling `stream_historical_events()` for multiple instruments, their data doesn't arrive together in order

#### **Real Example of the Problem**

```
Strategy wants data for 3 instruments starting from January 1st:
- Calls stream_historical_events() for EUR/USD data
- Calls stream_historical_events() for GBP/USD data
- Calls stream_historical_events() for USD/JPY data

What happens:
- EUR/USD data from 9:00 AM arrives
- USD/JPY data from 8:30 AM arrives (this is older!)
- GBP/USD data from 9:15 AM arrives
- More EUR/USD data from 8:45 AM arrives (this is even older!)

Result: Strategy gets completely mixed up about what time things happened
```

#### **What Goes Wrong**

- **Trading logic breaks**: Strategies that depend on time order stop working correctly
- **Testing becomes wrong**: Can't trust historical testing results
- **Hard to debug**: Very difficult to figure out what went wrong
- **Multi-instrument strategies fail**: Strategies that compare different instruments can't work properly
- **Analysis becomes unreliable**: Can't do proper analysis when data is out of order

### ### What We Need to Fix This

#### **Basic Requirements**

1. **Time always moves forward**: All data must come in time order, from oldest to newest
2. **Clear time boundaries**: Strategy should know if it's looking at historical data or live data
3. **Clean transitions**: When switching from historical to live data, it should be smooth
4. **Strategy knows the time**: Strategy should always know what time it's at
5. **Multiple instruments together**: Should be able to get data for many instruments at once, all in time order
6. **Coordinated delivery**: All instrument data should arrive mixed together in the right time sequence

#### **Requirements for Multiple Instruments**

1. **Ask for many instruments at once**: One request should be able to get data for multiple instruments
2. **Single time-ordered stream**: All instruments should send their data through one channel in time order
3. **Perfect timing**: System makes sure all instrument data arrives in the right time sequence
4. **All-or-nothing**: Either get data for all requested instruments, or none at all

### ### Possible Solution: Strategy Clock and Timelines

**A promising solution is to give each Strategy its own internal clock and let it manage multiple timelines that automatically stay in sync with this clock.**

#### **How This Would Work**

**1. Strategy Gets Its Own Clock**
- Each strategy has its own timer that tracks what time the strategy thinks it is
- All data must respect this timer
- Time always moves forward, never backward

**2. Timeline System**
- Each timeline represents data for one instrument (like EUR/USD bars or GBP/USD prices)
- All timelines automatically sync with the strategy's clock
- Multiple timelines can work together and deliver data in the right time order
- Can add or remove timelines anytime

**3. Timeline Features**
- **Flexible content**: Each timeline can have different types of data (prices, volumes, etc.)
- **Automatic sync**: All timelines automatically align with the strategy clock
- **Add anytime**: Can add new instrument timelines while strategy is running
- **Limited history**: New timelines added later will have less historical data (which is expected and OK)
- **Perfect order**: System makes sure all timeline data comes in the right time order

#### **Adding and Removing Timelines**

**Adding new instrument data:**
```
Strategy starts and adds EUR/USD timeline at time T1
Later, strategy adds GBP/USD timeline at time T2 (T2 is after T1)
GBP/USD timeline will only have data from T2 onwards (missing T1-T2 period)
This is expected and acceptable
```

**Timeline coordination:**
- All active timelines deliver data in time order relative to strategy clock
- Data from different instruments gets automatically mixed into one time-ordered sequence
- Strategy receives all data in perfect chronological order

**Removing timelines:**
```
Strategy can remove instrument timelines when no longer needed
```

#### **Benefits of This Approach**

**1. Perfect Time Order**
- Strategy clock ensures all data respects time progression
- Impossible to receive out-of-order data
- Clear time reference for all strategy operations

**2. Multiple Instruments Work Together**
- Multiple timelines automatically coordinate through shared strategy clock
- Data from different instruments delivered in correct time sequence
- Single time-ordered flow across all subscribed instruments

**3. Flexible Management**
- Timelines can be added/removed while strategy is running
- Strategy can adapt to changing needs
- Don't need to decide all instruments upfront

**4. Accepts Natural Limitations**
- Clear expectation that later-added timelines will have less history
- Prevents time paradoxes by accepting this natural limitation
- Strategy can make smart decisions about when to add new instruments

**5. Simple to Use**
- Single clock reference eliminates time confusion
- Timeline management provides clear, easy interface
- Automatic coordination reduces complexity for strategy developers

### ### Success Criteria

A good solution will:

- **Fix time paradoxes**: No strategy can get out-of-order data
- **Keep trading logic working**: Time-based trading strategies work reliably
- **Make development easier**: Clear, predictable time behavior
- **Enable solid testing**: Consistent historical data processing
- **Support live trading**: Smooth transition to real-time operations
- **Sync multiple instruments**: All instruments deliver data in unified time order
- **Enable multi-instrument strategies**: Support for comparing instruments, arbitrage, and portfolio strategies
- **Allow dynamic management**: Can add/remove instruments while strategy is running
- **Keep time clarity**: Strategy always knows what time it's at
- **Handle limitations gracefully**: Accept that later-added instruments will have less history

This problem needs a complete redesign that puts time consistency first, making sure trading strategies always operate in a logical time environment across all the instruments they're watching. The current methods like `stream_historical_events()`, `start_live_stream_with_history()`, and others need to be rethought to prevent the chronological ordering issues that break trading strategy logic.


# PERSPECTIVE SOLUTION


## PLANY

1. Each strategy need to have internal State machine, that reflects in each phase the strategy is in
	1. NOT_STARTED
		- after constructor run
		- here is the best time to request all initial event-feeds in `on_start` callback.
	2. When `start` function is invoked (it calls `on_start` callback, which is the right place for initial configuration of the strategy)

	2. STARTED
		- after `on_start` callback was executed
	4. HISTORICAL (eating historical events from event-feeds)
	5. TRANSITION (when there are no historical events)
	6. LIVE (when live data start to be processed)
	7. STOPPED (after `on_stop` was run)

3. Each Strategy keeps information about datetime of last event: `dt_last_event`
	- This is is for keeping chronological order of events
	- And each next event has to have `dt_event` equal / later then this `dt_last_event`.

4. Each strategy can be configured to receive events/data from multiple EventFeed(s).
	- We pop the first event from each EventFeed and the earliest `dt_event` Event will setup the historical clock of the Strategy.
		- From this datetime, the strategy starts running (it is like start-time of all historical data)
		- Then we will pop next event from all EventFeed(s) and process the next Event in chronological order

5. Strategy can add EventFeeds also later (when events from existing EventFeed(s) are already arriving and processed), but here all obsolete events will be ignored, as strategy is already running
and processing events and the timeline is fixed. That means, all obsolete events from EventFeed will be automatically removed and ignored and only relevant events (with dt_event >= strategy_clock) will be processed

----

Here we change the fundamental logic how strategy received historical / live data to EventFeed.

Tieto EventFeedy nam umoznuju dodavat data a Strategia si z nich vybera vzdy chronologicky
najmladsi event.



Strategia vie skoncit 2-ma sposobmi:
- Ked strategia spotrebuje vsetky eventy zo vsetkych event-feedov, tak vtedy automaticky skonci a zavola sa stop()
- Ked rucne zavolame stop()


CO teraz potrebuje je, upravit myslenie strategie pri praci s datami - ze budeme pridavat EventFeedy:
- a to bud na zaciatku v `on_start` - najstarsi event zo vsetkych event-feedov urci kde bude strategia zacinat
- alebo aj neskor (ale tam sa uz zahodia stare obsolete eventy)


## UPRAVY

UPRAVA 1: Odstranit stare metody pre pracu s datami


	Potom aj na urovni TradingEngine

	Potom aj na urovni MarketDataProvider (necham len class)


UPRAVA 2:

EventFeed

Kazdy event by mal taktiez vediet ci je historicky / live.
Ked sa minu vsetky historicke eventy zo vsetkych event-feedov,
tak vtedy prebehnut.

EventFeed by mal vediet signalizovat, ze caka na dalsie (buduce) data
	- iba v LiveMode sa caka na buduce data
	- ked poskytuje historicke data, vieme si nahliadnut (pop) dalsi event

EventFeed by mal vediet signalizovat, ked je na konci eventami (ze uz sme vsetky vycerpali, napr. v pripade historickych dat)



UPRAVA 3:

	Strategia by nemala robit priamo EventFeed-om, ale mala by si vediet vypytat:
		- request_event_feed(self, event_type: type, parameters: dict, provider)


	Tieto request sa potom budu delegovat na TradingEngine, ktory zabezpeci EventFeed od MarketDataProvidera a spristupni ho len pre danu strategiu.



	a zabezpeci distribuciu do jednotlivych


UPRAVA 4:

Je uplne jasne, ze kazda strategia ma vlastne:
- interny cas (jej beh moze zahrnat rozne historicke obdobia)
- event-feedy


UPRAVA 5:

Ak chceš porovnávať čas najbližšieho eventu zo všetkých feedov, musíš byť schopný nahliadnuť na ďalší event bez jeho odstránenia (peek()).

EventFeed musi mat metodu:
- peek()
- pop()
- remove_all_events_before(datetime)

UPRAVA 6:

🆕 2. Použitie heapq pre správne poradie
Prečo: Ak máš viac feedov, je efektívne použiť min-heap na výber najskoršieho eventu (podľa dt_event). Tento algoritmus zabezpečí optimálne triedenie v čase O(log N).


UPRAVA 7:

Poradie eventov (ak maju rovnaky `dt_event`), je podla poradia vyziadania eventu v strategii.
