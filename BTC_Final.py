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
        # every 1 hours
        self.period = 60 * 60
        self.options = {}
        self.close_price_history = []
        
        self.history_candles = CA.get_history_candles(6 * 30, self.period)
        if self.history_candles:
            for exchange in self.history_candles:
                for pair in self.history_candles[exchange]:
                    for candle in self.history_candles[exchange][pair]:
                        self.close_price_history.append(float(candle['close']))
            # CA.log(str(len(self.close_price_history)))
            # CA.log(str(self.close_price_history[-1]))
    
        self.rsi_length = 6 * 2
        self.MA_length = 6 * 5  #days
        self.counter = 0
        self.max_tolerant = 7 # tolerant 稀釋 buy 的次數

        # TD 
        self.raise_counter = 0
        self.fall_counter = 0

        # init action
        self.initBuy = False
        self.initSell = False

    def on_order_state_change(self, order):
        pass

    def get_RSI(self):
        RSI = talib.RSI(np.array(self.close_price_history), self.rsi_length)[-1]
        # CA.log("RSI value: " + str(RSI))
        return RSI

    def get_EMA(self, pre_EMA, period):
        cur_EMA = (pre_EMA * (period - 1) + self.close_price_history[-1] * 2) / (period + 1)
        return cur_EMA
        
    def get_MACD(self):
        macd, signal, hist = talib.MACD(np.array(self.close_price_history), fastperiod=12, slowperiod=26, signalperiod=9)
        # CA.log("Hist:" + str(hist[-1]))
        return hist

    def boolinger_bands(self):
        self.boolinger_alpha = 2.0
        self.MA = np.mean(self.close_price_history[-self.MA_length:])
        self.std = np.std(self.close_price_history[-self.MA_length:])
        bool_upper  = self.MA + self.boolinger_alpha * self.std
        bool_middle = self.MA
        bool_lower   = self.MA - self.boolinger_alpha * self.std
        return bool_upper, bool_middle, bool_lower

    def BBANDS(self):
        upper, middle, lower = talib.BBANDS(np.array(self.close_price_history), timeperiod=6 * 10, nbdevup=2, nbdevdn=2)
        return upper[-1], middle[-1], lower[-1]

    def get_Momentum(self):
        return talib.MOM(np.array(self.close_price_history), timeperiod=6*2)

    def trade(self, candles):
        # base基準貨幣, quote標價貨幣
        exchange, pair, base, quote = CA.get_exchange_pair()

        # update balance
        base_balance = CA.get_balance(exchange, base)
        quote_balance = CA.get_balance(exchange, quote)
        available_base_amount = base_balance.available
        available_quote_amount = quote_balance.available

        # update today close_price into self.close_price_history
        self.close_price_history.append(float(candles[exchange][pair][0]['close']))

        # calculate boolinger_bands
        BOOL_UPPER, BOOL_MIDDLE, BOOL_LOWER = self.BBANDS()

        # calculate MACD
        MACD_HIST = self.get_MACD()

        # calculate RSI
        RSI = self.get_RSI()
        
        # calculate Momentum
        MOMENTUM = self.get_Momentum()

        #######################################################################
        # Init buy and sell to avoid penalty of our strategy didn't buy atleast one time for the competition
        # Init Sell 
        self.init_amount = 1.2
        if self.initSell:
            self.initSell = False
            if available_base_amount > 0:
                CA.log('賣出 ' + base)
                CA.sell(exchange, pair, available_base_amount, CA.OrderType.MARKET)

        # Init Buy
        if not self.initBuy:
            CA.log('First blood')
            self.initBuy = True
            self.initSell = True
            if available_quote_amount >= self.init_amount * self.close_price_history[-1]:
                CA.log("買入" + base)
                CA.buy(exchange, pair, self.init_amount, CA.OrderType.MARKET)
        #######################################################################

        # Every period action ...
        amount = 1.1

        if self.close_price_history[-1] < self.close_price_history[-5]:
            self.raise_counter = 0
            self.fall_counter = self.fall_counter + 1
        elif self.close_price_history[-1] >= self.close_price_history[-5]:
            self.fall_counter = 0
            self.raise_counter = self.raise_counter + 1

        if self.fall_counter == 15:
            self.fall_counter = 0
            if available_quote_amount >= amount * self.close_price_history[-1]:
                price = self.close_price_history[-1] * 0.98
                CA.buy(exchange, pair, amount, CA.OrderType.LIMIT, price)
        elif self.raise_counter == 13:
            self.raise_counter = 0
            if available_base_amount > 0:
                CA.sell(exchange, pair, available_base_amount, CA.OrderType.MARKET)

        # MACD
        # if MACD_HIST[-2] > 0 and MACD_HIST[-1] < 0:
        #     self.counter  = self.counter + 1
        #     if self.counter % self.max_tolerant == 0 and available_quote_amount >= amount * self.close_price_history[-1]:
        #         CA.buy(exchange, pair, amount, CA.OrderType.MARKET)
        # elif MACD_HIST[-2] < 0 and MACD_HIST[-1] > 0:
        #     if available_base_amount > 0:
        #         CA.sell(exchange, pair, available_base_amount, CA.OrderType.MARKET)

        # Momentum
        # if MOMENTUM[-1] > 0 and MOMENTUM[-2] < 0:
        #     self.counter  = self.counter + 1            
        #     if available_quote_amount >= amount * self.close_price_history[-1]:
        #         CA.buy(exchange, pair, amount, CA.OrderType.MARKET)
        # elif MOMENTUM[-1] < 0 and MOMENTUM[-2] > 0:            
        #     if available_base_amount > 0:
        #         CA.sell(exchange, pair, available_base_amount, CA.OrderType.MARKET)

        # RSI 
        # if RSI < 30:
        #     self.counter  = self.counter + 1
        #     if  available_quote_amount >= amount * self.close_price_history[-1]:
        #         CA.buy(exchange, pair, amount, CA.OrderType.MARKET)        
        # elif RSI > 70:
        #     if available_base_amount > 0:
        #         CA.sell(exchange, pair, available_base_amount, CA.OrderType.MARKET)