class Strategy():

    def __setitem__(self, key, value):
        self.options[key] = value

    def __getitem__(self, key):
        return self.options.get(key, '')

    def __init__(self):
        self.subscribedBooks = {
            'Binance': {
                'pairs': ['BTC-USDT'],
            },
        }
        self.period = 60 * 15
        self.options = {}

        # user defined class attribute
        self.last_type = 'sell'
        self.last_rsi = None
        self.last_cross_status = None
        self.close_price_trace = np.array([])
        self.ma_long = 10
        self.ma_short = 5
        self.rsi_length = 100

        self.initial_buy = 0.1
        self.last_buy = self.initial_buy
        self.last_buy_price = None
        self.buying_amount = 0
        self.back_to_fourty = True
        self.highest_buying = 0
        self.over_sell = 20
        self.over_buy = 80
        self.buying_spree = 0
        self.first_try = True

    def on_order_state_change(self, order):
        pass

    # Moving Average
    def get_MA(self):
        short_MA = talib.SMA(self.close_price_trace[-self.ma_long:], self.ma_short)[-1]
        long_MA = talib.SMA(self.close_price_trace[-self.ma_long:], self.ma_long)[-1]
        if np.isnan(short_MA) or np.isnan(long_MA):
            return None
        if short_MA > long_MA:
            return 1
        return 2

    # RSI
    def get_RSI(self):
        rsi = talib.RSI(self.close_price_trace, 14)[-1]
        Log("rsi " + str(rsi) + " " + str(self.last_rsi))
        if rsi is not np.nan:
            if rsi > float(self.over_buy):
                return True, rsi
            if rsi < float(self.over_sell):
                return False, rsi

            return None, rsi

    def get_MACD(self):
        macd, signal, hist = talib.MACD(self.close_price_trace, fastperiod=12, slowperiod=26, signalperiod=9)
        return macd[-1] - signal[-1]

    def sell(self, exchange, pair, close_price, rsi_value, amount=None):
        if amount is None:
            amount = self.buying_amount
            amount = min(self.buying_amount, self.targetCurrency_amount)
        if amount <= self.buying_amount:
            self.highest_buying = 0
            self.last_type = 'sell'
            self.last_buy = self.initial_buy
            output =    [
                    {
                    'exchange': exchange,
                    'amount': -amount,
                    'price': -1,
                    'type': 'MARKET',
                    'pair': pair,
                    }
            ]
            Log("sell {}, rsi {}".format(amount, rsi_value))
            self.buying_amount -= amount
        else:
            output = []
        return output

    def buy(self, exchange, pair, close_price, rsi_value, amount=None, record = True):
        if amount is None:
            amount = min(int(max(self.last_buy + 1, self.last_buy * 1.8)),  self.initial_buy*8)
        max_amount = self.baseCurrency_amount // close_price
        amount = min(amount, max_amount)
        if amount == 0:
            return []
        self.last_buy_price = close_price
        if close_price > self.highest_buying:
            self.highest_buying = close_price
        if record:
            self.last_buy = amount
        self.buying_amount += amount
        self.last_type = 'buy'
        Log("buy  {}, rsi {}".format(amount, rsi_value))
        return  [
                {
                    'exchange': exchange,
                    'amount': amount,
                    'price': -1,
                    'type': 'MARKET',
                    'pair': pair,
                }
            ]
            
    def trade(self, information):

        output = [] 
        exchange = list(information['candles'])[0]
        pair = list(information['candles'][exchange])[0]
        close_price = information['candles'][exchange][pair][0]['close']

        self.targetCurrency = pair.split('-')[0]
        self.baseCurrency = pair.split('-')[1]
        
        self.baseCurrency_amount = self['assets'][exchange][self.baseCurrency] 
        self.targetCurrency_amount = self['assets'][exchange][self.targetCurrency]


        # add latest price into trace
        self.close_price_trace = np.append(self.close_price_trace, [float(close_price)])
        # only keep max length of ma_long count elements
        self.close_price_trace = self.close_price_trace[-self.rsi_length:]
        rsi, rsi_value = self.get_RSI()

        if self.first_try:
            self.first_try = False
            return self.buy(exchange, pair, close_price, rsi_value, amount=1, record=False)
        if not self.back_to_fourty:
            if rsi_value > 40:
                self.back_to_fourty = True

        if self. last_type == 'buy' and float(close_price) < 0.9 * self.last_buy_price:
            if  rsi_value <= 40:
                output = self.buy(exchange, pair, close_price, rsi_value)
            else:
                output = self.buy(exchange, pair, close_price, rsi_value, amount=self.initial_buy)
        elif self.last_rsi != False and rsi  == False and self.back_to_fourty:
            output = self.buy(exchange, pair, close_price, rsi_value)
            self.back_to_fourty =False
        elif self.last_rsi != True and rsi == True and self.buying_amount > 0:
            output = self.sell(exchange, pair, close_price, rsi_value)
            self.buying_spree = 0
        elif self.last_buy_price != None and float(close_price) > 1.05 *  self.last_buy_price:
            if self.buying_spree > 4:
                output = self.sell(exchange, pair, close_price, rsi_value)
                self.buying_spree = 0
            output = self.buy(exchange, pair, close_price, rsi_value)
            self.buying_spree += 1
        
        self.last_rsi = rsi