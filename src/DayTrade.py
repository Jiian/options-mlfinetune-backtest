import pandas as pd
from datetime import time
from dateutil.relativedelta import relativedelta

class DayTrade:
    def __init__(self, strategy, model_num, AUM, df_options, commission_dollars = 0.15, max_risk = 0.025, interval = 5):
        self.params = strategy.get_models(model_num)
        self.df_options = df_options
        self.interval = interval

        self.commission_dollars = commission_dollars
        self.max_risk = max_risk
        self.AUM = AUM

        enter_long, exit_long, enter_short, exit_short = strategy.entry_exit_signals(model_num = model_num)
        self.enter_long = enter_long
        self.exit_long = exit_long
        self.enter_short = enter_short
        self.exit_short = exit_short

    def trade(self):
        max_risk_dollars = self.AUM * self.max_risk

        # Initiations
        position = 0
        trades = list()
        tradeable_instances = list(self.df_options.loc[:, "time"].unique())
        prev_instance = tradeable_instances[0] - relativedelta(minutes = self.interval)
        for trade_instance in tradeable_instances:
            df_options_instance = self.df_options[self.df_options["time"] == trade_instance]

            match position:
                case 0:
                    if trade_instance.time() < time(14, 30):
                        if self.enter_long[(self.enter_long.index < trade_instance)].iloc[-1]:
                            metadata = self.open_long_trade(df_options_instance, self.params, max_risk_dollars)
                            if metadata is None:
                                continue # Skip if trade could not be opened
                            else:
                                trades.append(metadata)
                                position = 1
                        elif self.enter_short[(self.enter_short.index < trade_instance)].iloc[-1]:
                            metadata = self.open_short_trade(df_options_instance, self.params, max_risk_dollars)
                            if metadata is None:
                                continue # Skip if trade could not be opened
                            else:
                                trades.append(metadata)
                                position = -1
                case 1:
                    latest_trade = trades[-1]
                    # exit long criteria
                    exit_signal = self.exit_long[(self.exit_long.index < trade_instance) & (self.exit_long.index >= prev_instance)].any()
                    # stoploss hit
                    stoploss_hit = self.check_long_stoploss(df_options_instance, latest_trade, self.params)
                    # checks
                    if exit_signal or stoploss_hit:
                        trades[-1] |= self.close_long_trade(df_options_instance, latest_trade, reason = "exit_criteria" if exit_signal else "stoploss")
                        position = 0
                case -1:    
                    latest_trade = trades[-1]
                    # exit short criteria
                    exit_signal = self.exit_short[(self.exit_short.index < trade_instance) & (self.exit_short.index >= prev_instance)].any()
                    # stoploss hit
                    stoploss_hit = self.check_short_stoploss(df_options_instance, latest_trade, self.params)
                    # checks
                    if exit_signal or stoploss_hit:
                        trades[-1] |= self.close_short_trade(df_options_instance, latest_trade, reason = "exit_criteria" if exit_signal else "stoploss")
                        position = 0
                case _:
                    raise ValueError("Invalid position value.")
        if position == 1:
            trades[-1] |= self.close_long_trade(df_options_instance, latest_trade, reason = "end_of_time")
        elif position == -1:
            trades[-1] |= self.close_short_trade(df_options_instance, latest_trade, reason = "end_of_time")
        if len(trades) > 0:
            trades = pd.DataFrame(trades)
        else:
            trades = pd.DataFrame(columns = ['entry_time', 'direction', 'entry_spot', 'entry_atm_strike',
                'leg1_strike', 'leg2_strike', 'entry_leg1_price', 'entry_leg2_price',
                'entry_unit_spread', 'entry_unit_maxloss', 'contracts', 'stoploss',
                'exit_time', 'exit_spot', 'exit_leg1_price', 'exit_leg2_price',
                'exit_unit_spread', 'exit_reason', 'unit_pnl_gross', 'pnl'])
        return trades

    # Helper functions
    @staticmethod
    def find_closest_strike(strike, df_options_instance): return df_options_instance.loc[abs(df_options_instance.loc[:, "strike"] - strike).idxmin(), :]

    def close_long_trade(self, df_options_instance, latest_trade, reason):
        # Current info
        current_spot = df_options_instance.loc[:, "stockPrice"].unique()[0]

        # Exit prices
        leg1 = df_options_instance[df_options_instance["strike"] == latest_trade["leg1_strike"]].iloc[0]
        leg2 = df_options_instance[df_options_instance["strike"] == latest_trade["leg2_strike"]].iloc[0]
        leg1_price = leg1["putAskPrice"]
        leg2_price = leg2["putBidPrice"]

        # Info
        exit_price = leg1_price - leg2_price
        unit_pnl_gross = latest_trade["entry_unit_spread"] - exit_price # credit spread
        pnl = unit_pnl_gross * latest_trade["contracts"] * 100 - self.commission_dollars * 4 * latest_trade["contracts"]

        # Update trade info
        metadata_update = {
            "exit_time": df_options_instance["time"].iloc[0],
            "exit_spot": current_spot,
            "exit_leg1_price": leg1_price,
            "exit_leg2_price": leg2_price,
            "exit_unit_spread": exit_price,
            "exit_reason": reason,
            "unit_pnl_gross": unit_pnl_gross,
            "pnl" : pnl
        }

        return metadata_update

    def close_short_trade(self, df_options_instance, latest_trade, reason):
        # Current info
        current_spot = df_options_instance.loc[:, "stockPrice"].unique()[0]

        # Exit prices
        leg1 = df_options_instance[df_options_instance["strike"] == latest_trade["leg1_strike"]].iloc[0]
        leg2 = df_options_instance[df_options_instance["strike"] == latest_trade["leg2_strike"]].iloc[0]
        leg1_price = leg1["callAskPrice"]
        leg2_price = leg2["callBidPrice"]

        # Info
        exit_price = leg1_price - leg2_price
        unit_pnl_gross = latest_trade["entry_unit_spread"] - exit_price # credit spread
        pnl = unit_pnl_gross * latest_trade["contracts"] * 100 - self.commission_dollars * 4 * latest_trade["contracts"]

        # Update trade info
        metadata_update = {
            "exit_time": df_options_instance["time"].iloc[0],
            "exit_spot": current_spot,
            "exit_leg1_price": leg1_price,
            "exit_leg2_price": leg2_price,
            "exit_unit_spread": exit_price,
            "exit_reason": reason,
            "unit_pnl_gross": unit_pnl_gross,
            "pnl" : pnl
        }

        return metadata_update

    def check_long_stoploss(self, df_options_instance, latest_trade, params):
        stoploss = latest_trade['stoploss']
        leg1_price = df_options_instance[df_options_instance.loc[:, "strike"] == latest_trade['leg1_strike']].iloc[0].loc["putAskPrice"]
        leg2_price = df_options_instance[df_options_instance.loc[:, "strike"] == latest_trade['leg2_strike']].iloc[0].loc["putBidPrice"]
        current_price = leg1_price - leg2_price
        return current_price >= stoploss

    def check_short_stoploss(self, df_options_instance, latest_trade, params):
        stoploss = latest_trade['stoploss']
        leg1_price = df_options_instance[df_options_instance.loc[:, "strike"] == latest_trade['leg1_strike']].iloc[0].loc["callAskPrice"]
        leg2_price = df_options_instance[df_options_instance.loc[:, "strike"] == latest_trade['leg2_strike']].iloc[0].loc["callBidPrice"]
        current_price = leg1_price - leg2_price
        return current_price >= stoploss

    def open_long_trade(self, df_options_instance, params, max_risk_dollars):
        # Current info
        current_spot = df_options_instance.loc[:, "stockPrice"].unique()[0]
        current_atm = self.find_closest_strike(current_spot, df_options_instance)
        leg1 = self.find_closest_strike(current_atm.loc["strike"] - params["opt_leg1_dollar_from_atm"], df_options_instance)
        leg1_strike = leg1.loc["strike"]
        leg2 = self.find_closest_strike(leg1_strike - params["opt_leg2_dollar_from_leg1"], df_options_instance)
        leg2_strike = leg2.loc["strike"]
        
        # Positioning
        unit_spread = leg1.loc["putBidPrice"] - leg2.loc["putAskPrice"]
        unit_maxloss = leg1.loc["strike"] - leg2.loc["strike"] - unit_spread
        contracts = int(max_risk_dollars / 100 / unit_maxloss * 0.50) # set a 50% cap on max_risk - while avoiding large contract sizes
        stoploss = unit_spread + unit_spread * params["stoploss_pct_of_maxprofit"]

        # Validations
        try:
            # assert leg1.loc["putBidSize"] > contracts and leg2.loc["putAskSize"] > contracts, "One of the legs is not tradable due to bid/ask size smaller than intended entry."
            assert unit_spread > 0.01, "The spread is not positive."
            assert leg1.loc["putAskPrice"] - leg2.loc["putBidPrice"] < stoploss, f"Unfavourable spread for entry: Entry spread: {unit_spread}, Exit spread: {leg1.loc['putAskPrice'] - leg2.loc['putBidPrice']}, Stoploss: {stoploss}"
        except AssertionError as e:
            return None

        # Metadata
        metadata = {
            "entry_time": df_options_instance["time"].iloc[0],
            "direction" : 1,
            "entry_spot": current_spot,
            "entry_atm_strike": current_atm.loc["strike"],
            "leg1_strike": leg1_strike,
            "leg2_strike": leg2_strike,
            "entry_leg1_price": leg1.loc["putBidPrice"],
            "entry_leg2_price": leg2.loc["putAskPrice"],
            "entry_unit_spread": round(unit_spread, 6),
            "entry_unit_maxloss": round(unit_maxloss, 6),
            "contracts": contracts,
            "stoploss": round(stoploss, 6)
        }

        return metadata

    def open_short_trade(self, df_options_instance, params, max_risk_dollars):
        # Current info
        current_spot = df_options_instance.loc[:, "stockPrice"].unique()[0]
        current_atm = self.find_closest_strike(current_spot, df_options_instance)
        leg1 = self.find_closest_strike(current_atm.loc["strike"] + params["opt_leg1_dollar_from_atm"], df_options_instance)
        leg1_strike = leg1.loc["strike"]
        leg2 = self.find_closest_strike(leg1_strike + params["opt_leg2_dollar_from_leg1"], df_options_instance)
        leg2_strike = leg2.loc["strike"]
        
        # Positioning
        unit_spread = leg1.loc["callBidPrice"] - leg2.loc["callAskPrice"]
        unit_maxloss = -(leg1.loc["strike"] - leg2.loc["strike"]) - unit_spread
        contracts = int(max_risk_dollars / 100 / unit_maxloss * 0.50) # set a 50% cap on max_risk - while avoiding large contract sizes
        stoploss = unit_spread + unit_spread * params["stoploss_pct_of_maxprofit"]

        # Validations
        try:
            # assert leg1.loc["callBidSize"] > contracts and leg2.loc["callAskSize"] > contracts, "One of the legs is not tradable due to bid/ask size smaller than intended entry."
            assert unit_spread > 0.01, "The spread is not positive."
            assert leg1.loc["callAskPrice"] - leg2.loc["callBidPrice"] < stoploss, f"Unfavourable spread for entry: Entry spread: {unit_spread}, Exit spread: {leg1.loc['callAskPrice'] - leg2.loc['callBidPrice']}, Stoploss: {stoploss}"
        except AssertionError as e:
            return None

        # Metadata
        metadata = {
            "entry_time": df_options_instance["time"].iloc[0],
            "direction" : -1,
            "entry_spot": current_spot,
            "entry_atm_strike": current_atm.loc["strike"],
            "leg1_strike": leg1_strike,
            "leg2_strike": leg2_strike,
            "entry_leg1_price": leg1.loc["putBidPrice"],
            "entry_leg2_price": leg2.loc["putAskPrice"],
            "entry_unit_spread": round(unit_spread, 6),
            "entry_unit_maxloss": round(unit_maxloss, 6),
            "contracts": contracts,
            "stoploss": round(stoploss, 6)
        }

        return metadata