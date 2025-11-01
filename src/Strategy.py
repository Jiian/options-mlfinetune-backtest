import pandas as pd
import numpy as np
import ta
from itertools import product

class Strategy:
    def __init__(self):
        self.params_grid = {
            "fast": [5, 10, 20], #sma|rsi|macd
            "slow_mult": [2, 3, 5], # sma|rsi|macd, for ATR also
            "rsi_threshold": [60, 70], #rsi only
        }

        self.tech_indicators = None
        self.models = [{list(self.params_grid.keys())[i] : x[i] for i in range(len(x))} for x in list(product(*self.params_grid.values()))]

    def compute_tech_indicators(self, df_stock, ret = False):
        tech_indicators = dict()
        for params in product(*self.params_grid.values()):
            params = {list(self.params_grid.keys())[i] : params[i] for i in range(len(params))}

            fast = params['fast']
            slow = params['fast'] * params["slow_mult"]
            tech_indicators[f"sma_{fast}"] = ta.trend.SMAIndicator(df_stock['close'], window=fast).sma_indicator()
            tech_indicators[f"sma_{slow}"] = ta.trend.SMAIndicator(df_stock['close'], window=slow).sma_indicator()
            tech_indicators[f"rsi_{slow}"] = ta.momentum.RSIIndicator(df_stock['close'], window=slow).rsi()
            tech_indicators[f"macdsignal_{fast}_{slow}"] = ta.trend.MACD(df_stock['close'], window_fast=fast, window_slow=slow).macd_signal()
            tech_indicators[f"macddiff_{fast}_{slow}"] = ta.trend.MACD(df_stock['close'], window_fast=fast, window_slow=slow).macd_diff()
            tech_indicators[f"atr_{slow}"] = ta.volatility.AverageTrueRange(df_stock['high'], df_stock['low'], df_stock['close'], window=slow).average_true_range()
        tech_indicators = pd.DataFrame(tech_indicators).dropna()

        self.tech_indicators = tech_indicators
        if ret:
            return tech_indicators
    
    def entry_exit_signals(self, params = None, model_num = None):
        if params is None:
            params = self.models[model_num]
            if model_num is None:
                raise ValueError("Either params or model_num must be provided.")

        enter_long = pd.Series(np.all([
            (self.tech_indicators[f"sma_{params['fast']}"] > self.tech_indicators[f"sma_{params['fast'] * params['slow_mult']}"]), # SMA_fast > SMA_slow
            (self.tech_indicators[f"macddiff_{params['fast']}_{params['fast'] * params['slow_mult']}"] > 0), # MACD diff > 0
            (self.tech_indicators[f"rsi_{params['fast'] * params['slow_mult']}"] <= params["rsi_threshold"]) # RSI not > 60
        ], axis = 0), index = self.tech_indicators.index)

        exit_long = pd.Series(np.any([
            # RSI > 60
            self.tech_indicators[f"rsi_{params['fast'] * params['slow_mult']}"] > params["rsi_threshold"]
        ], axis = 0), index = self.tech_indicators.index)

        enter_short = pd.Series(np.all([
            (self.tech_indicators[f"sma_{params['fast']}"] < self.tech_indicators[f"sma_{params['fast'] * params['slow_mult']}"]), # SMA_fast > SMA_slow
            (self.tech_indicators[f"macddiff_{params['fast']}_{params['fast'] * params['slow_mult']}"] < 0), # MACD diff > 0
            (self.tech_indicators[f"rsi_{params['fast'] * params['slow_mult']}"] >= 100 - params["rsi_threshold"]) # RSI not > 60
        ], axis = 0), index = self.tech_indicators.index)

        exit_short = pd.Series(np.any([
            # RSI > 60
            self.tech_indicators[f"rsi_{params['fast'] * params['slow_mult']}"] < 100 - params["rsi_threshold"]
        ], axis = 0), index = self.tech_indicators.index)

        return enter_long, exit_long, enter_short, exit_short