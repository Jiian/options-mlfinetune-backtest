# Overview and Findings

## 01 Data ingestions.ipynb
I am posed with the difficulty of limited API calls, having limited storage and computing capacity, and the speed of calling the API. Hence, through out this project, I have decided to focus on only trading days that fall on Fridays since January 2022.

The class defined in `src/DataUpdateModule.py`, allows a simple call to retrieve and save all the necessary data for any trading day. This class is utilised in this notebook.

## 02 EDA.ipynb
I started the analysis by visualising some of the intraday trading data for both the underlying stock and the options.

<img src="./attachments/02 eda 2.png" width="600"/>

- It is observed that trading volume for both Call and Put across strikes increase almost monotonically throughout the day.
- In the case that a systematic trading strategy was to be formed using options liquidity as signal, we should expect a skew of trades with respect to time.
- For the first Friday of 2022, put trading volumes seem to be clearly dominating the options activity, with a small rapid growth happening mid-day.

<img src="./attachments/02 eda 1.png" width="600"/>

- Given the price chart of the underlying, I have formulated a goal to test a strategy that captures one or two big trends intraday.
- The goal is to identify big trending periods, and avoid sideways regimes. I will attempt to do this through the use of underlying stock price technical indicators to inform a trade signal, and options data only for execution.
- ML will be used for hyperparameters tuning.

<img src="./attachments/02 eda 3.png" width="600"/>
<img src="./attachments/02 eda 4.png" width="600"/>

- Further checks (for completeness) show that the ITM option prices are almost linear with respect to the strike throughout the day (in both large and zoomed scale). This is expected since 0DTE options should have limited extrinsic value.
- Bid/ask spreads for any option instrument are significantly wider around >$6 strikes OTM for most of the day during the first Friday of 2022. Any strategies should minimise trading these strikes.

## 03 Trade Analysis using Jan'2022.ipynb

At this stage, I started to plan the implementation of a simple trading strategy.

In all of the following "entering long" refers to entering a bull put credit spread and "entering short" refers to entering a bear call credit spread.

The strategy:
```
Enter long when
1. SMA_fast > SMA_slow
2. MACD_diff > 0
3. RSI not overbought

Exit long when
1. RSI shows overbought

Enter short when
1. SMA_fast < SMA_slow
2. MACD_diff < 0
3. RSI not oversold

Exit short when
1. RSI shows oversold
```

This strategy is then branched into "models", in which each model simply sets a unique configuration to implement the strategy.

Example configurations:
```
{
    # used in TA
    "fast": [5, 10, 20, 30], #sma|rsi|macd
    "slow_mult": [2, 3], #sma|rsi|macd, ATR
    "rsi_threshold": [60, 70], #rsi only

    # used in trade env
    "opt_leg1_dollar_from_atm" : [0, 1, 2, 5],
    "opt_leg2_dollar_from_leg1" : [1, 2, 5, 10],
    "stoploss_pct_of_maxprofit" : [.1, .5],
}
```

The following chart shows the pnl from each "model" in the four Fridays of Jan'22. Each line represents a combination of the configurations set above (e.g. fast=5, slow_mult=3, rsi_threshold=60, opt_leg1_dollar_from_atm=0, opt_leg2_dollar_from_leg1=1, stoploss_pct_of_maxprofit=0.5)

<img src="./attachments/03 trade analysis 1.png" width="600"/>

While most of the lines lie below breakeven, there are a significant number of models with positive P&L. The goal now lies with choosing the right model to trade using.

This goal is achieved in two steps:

1. Refining the choice of hyperparameters
2. Devising a method to choose the best model that will continue to perform well in the immediate future.

In the same notebook, I analysed the impact of each hyperparameter.

<img src="./attachments/03 trade analysis 2.png" width="600"/>
<img src="./attachments/03 trade analysis 3.png" width="600"/>

Through Feature Importance and Partial Dependence Plots, it is observed that the strikes of the two options positions and the fast window for technical analysis impact P&L significantly more than the other hyperparameters.

The trend is also observable through PDP for the regions in the hyperparameter space that produces a higher P&L on average.

Using this information, I further refined the choices I am providing in the hyperparameter grid.

## 04 Walk-forward test.ipynb

