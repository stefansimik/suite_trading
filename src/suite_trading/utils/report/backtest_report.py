import logging
from decimal import Decimal
from typing import List

from suite_trading.domain.order.order_enums import OrderTriggerType, TradeDirection, OrderSide
from suite_trading.domain.order.order_state import OrderState
from suite_trading.domain.order.orders import Order

logger = logging.getLogger(__name__)

class Trade:
    def __init__(self, order: Order):
        self._order_entry: List[Order] = [order]
        self._order_exit: List[Order] = []


    @property
    def order_entry(self) -> List[Order]:
        return self._order_entry

    @property
    def order_exit(self) -> List[Order]:
        return self._order_exit

    @property
    def trade_id(self):
        return self._order_entry[0].trade_id

    def get_pnl(self) -> Decimal:
        pnl: Decimal = Decimal('0')
        for o in self._order_entry:
            for e in o.executions:
                if e.side == OrderSide.BUY:
                    pnl -= e.net_value
                else:
                    pnl += e.net_value
        for o in self._order_exit:
            for e in o.executions:
                if e.side == OrderSide.BUY:
                    pnl -= e.net_value
                else:
                    pnl += e.net_value
        return pnl

class BacktestReport:
    def __init__(self, orders: dict[str, Order], custom_logger: logging.Logger = None):
        self.custom_logger = custom_logger
        if not isinstance(orders, dict):
            raise ValueError(f"orders must be a dict[str, Order], but is {type(orders)}")
        self.orders = orders
        self.trades: dict[str, Trade] = {}

    def create_report(self) -> List[str]:
        self.log().debug("start calculating report")
        report = []
        #
        report.append(f"Orders: #{len(self.orders)}")
        self._build_trades()

        report.append(f"Trades: {len(self.trades)}")


        self.log().debug("end calculating report")
        return report

    def print_report(self):
        r = self.create_report()
        self.log().debug("+----------- Report start ------------")
        for l in r:
            self.log().debug(f"| {l}")
        self.log().debug("+----------- Report end ------------")

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



