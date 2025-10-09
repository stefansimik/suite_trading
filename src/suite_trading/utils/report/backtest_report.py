import logging
from decimal import Decimal
from typing import List

from suite_trading.domain.order.execution import Execution
from suite_trading.domain.order.order_enums import OrderTriggerType, TradeDirection, OrderSide
from suite_trading.domain.order.order_state import OrderState
from suite_trading.domain.order.orders import Order

logger = logging.getLogger(__name__)


def _gross_value(e: Execution) -> Decimal:
    return e.gross_value * e.instrument.contract_value_multiplier


class Trade:
    def __init__(self, order: Order):
        self.__order_entry: List[Order] = [order]
        self.__order_exit: List[Order] = []
        self.pnl: Decimal | None = None

    @property
    def order_entry(self) -> List[Order]:
        return self.__order_entry

    @property
    def order_exit(self) -> List[Order]:
        return self.__order_exit

    @property
    def trade_id(self):
        return self.__order_entry[0].trade_id

    def add_order_entry(self, order: Order):
        self.__order_entry.append(order)
        self.__reset()

    def add_order_exit(self, order: Order):
        self.order_exit.append(order)
        self.__reset()

    def __reset(self):
        self.pnl = None

    def get_pnl(self) -> Decimal:
        _pnl: Decimal = self.pnl
        if _pnl is not None:
            return _pnl
        _pnl = Decimal('0')
        for o in self.__order_entry:
            for e in o.executions:
                if e.side == OrderSide.BUY:
                    _pnl = _pnl - _gross_value(e) - e.commission
                else:
                    _pnl = _pnl + _gross_value(e) - e.commission
        for o in self.__order_exit:
            for e in o.executions:
                if e.side == OrderSide.BUY:
                    _pnl = _pnl - _gross_value(e) - e.commission
                else:
                    _pnl = _pnl + _gross_value(e) - e.commission
        self.pnl = _pnl
        return _pnl

class BacktestReport:
    """
    Usage:
        After engine.start() was performed and simulation is ready, call:

        BacktestReport(broker.orders).print_report()

        or

        report = BacktestReport(broker.orders).create_report()
        # do what you need with the string lines

    Parameters:
        orders: dict[str, Order]
            the dict of orders from simulation broker
        custom_logger: logging.Logger
            custom logger for printing the report
    """
    def __init__(self, orders: dict[str, Order], custom_logger: logging.Logger = None):
        self.custom_logger = custom_logger
        if not isinstance(orders, dict):
            raise ValueError(f"orders must be a dict[str, Order], but is {type(orders)}")
        self.orders = orders
        self.trades: dict[str, Trade] = {}

    def create_report(self) -> List[str]:
        self.log().debug("start calculating report")
        self._build_trades()
        report =     [f"Orders  : {len(self.orders)}     Trades : {len(self.trades)}"]
        winner = len ( {k: v for k, v in self.trades.items() if v.get_pnl() >= Decimal('0')} )
        loser = len({k: v for k, v in self.trades.items() if v.get_pnl() < Decimal('0')})
        report.append(f"Winner  : {winner}     Loser: {loser}")
        winrate = 0 if winner <= 0 else (winner / len(self.trades)) * 100
        report.append(f"Win rate: {winrate:.1f}%")
        l = list()
        win_sum = sum({v.get_pnl() for v in self.trades.values() if v.get_pnl() >= Decimal('0')})
        lose_sum = sum({v.get_pnl() for v in self.trades.values() if v.get_pnl() < Decimal('0')})
        pf = "n/a" if lose_sum == 0 else win_sum / lose_sum * -1
        report.append(f"PF      : {pf:.2f}   W/L PnL : {win_sum:.2f} / {lose_sum:.2f}")

        self.log().debug("end calculating report")
        return report

    def print_report(self):
        r = self.create_report()
        self.log().debug("+-------------- Report start ---------------")
        for l in r:
            self.log().debug(f"| {l}")
        self.log().debug("+-------------- Report end -----------------")

    def log(self) -> logging.Logger:
        if self.custom_logger is not None:
            return self.custom_logger
        else:
            return logger

    def _build_trades(self):
        """
        creates Trades with entry and exit orders.
        Orders must be connected
        :return:
        """
        unprocessed_orders = list( self.orders.copy().values() )
        filled_entry_order = list({k: v for k, v in self.orders.items() if v.trade_direction == TradeDirection.ENTRY and v.state == OrderState.FILLED }.values())
        for o in filled_entry_order:
            if not self.trades.__contains__(o.trade_id):
                t = Trade(o)
                self.trades[o.trade_id] = t
                unprocessed_orders.remove(o)
                lst = list({k: v for k, v in self.orders.items() if v.trade_id == o.trade_id and v.id != o.id and v.trade_direction == TradeDirection.ENTRY }.values())
                for l in lst:
                    t.order_entry.append(l)
                    unprocessed_orders.remove(l)
                # exits orders
                lst_exit = list({k: v for k, v in self.orders.items() if v.trade_id == o.trade_id and v.trade_direction == TradeDirection.EXIT}.values())
                for e in lst_exit:
                    t.order_exit.append(e)
                    unprocessed_orders.remove(e)
        # check that all orders are processed (rest was not marked properly)
        if len(unprocessed_orders) > 0:
            for o in unprocessed_orders:
                logger.warning(f"Order could not be matched to a trade: {o}")



