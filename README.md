# Task Statement
This project explores how to systematically trade 0DTE SPY options using bear call and bull put spreads to capture intraday momentum. The goal is to build an ML- or rules-based model that identifies optimal entry and exit points, manages risk and position sizing, and determines the best strike width for each spread.

The main challenge lies in balancing risk control (max loss, commissions, time constraints) with profit optimisation, while handling the high-frequency, short-duration nature of intraday options trading.

# Overview and Findings

## 01 Data ingestions.ipynb
I am posed with the difficulty of limited API calls, having limited storage and computing capacity, and the speed of calling the API. Hence, throughout this project, I have decided to focus on only **trading days that fall on Fridays** since January 2022. Options data (and trading) is also only done at a **5-min interval** from 0930 to 1500H Eastern Time (ET).

The class defined in [`src/DataUpdateModule.py`](./src/DataUpdateModule.py), allows a simple call to retrieve and save all the necessary data for any trading day. This class is utilised in this notebook.

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

The strategy is defined in code in [`src/Strategy`](./src/Strategy). The trading mechanism, environment and configurations are defined in [`src/DayTrade`](./src/DayTrade), it is named as such because every run of the DayTrade.trade() method runs a full day of trading.

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

## 04 Walk-forward test 2022.ipynb

In the walk-forward test, I chose the "best" model by testing each model with the market activity of previous month, in order to determine which model to use for the current month of interest. (e.g. At the beginning of June, before market opens, I test each of the 400+ models with the trading days in May, then select the "best" model say, model #52 which will be used to trade June)

Selection of the "best" model: In my current implementation, I select the model that has produced the highest $Average(PnL) / StdDev(PnL)$ across different trading days in the training month. The result could be improved if we have traded more days rather than only Fridays.

<img src="./attachments/04 walk-fwd 1.png" width="600"/>

The equity curve for Feb'22 to Dec'22 seems to produce consistent returns only in certain months. At this juncture, the ideal action is to investigate the data to identify the driver of profit - which we should have enough data for as there are two very clear regimes (one of breakeven P&L and one of consistent profits).

I shall keep this on a to-do list given the lack of time for this task.

<img src="./attachments/04 walk-fwd 3.png" width="600"/>

The PDP for 2022 (excluding Jan) continue to suggest a similar relationship between the hyperparameters and the eventual profit as per what is suggested in the previous notebook investigating only Jan'22 data.

No changes were made to the strategy at this point.

## 05 Walk-forward test full.ipynb

Walk forward test is being done for the period of Feb'22 to Oct'25, for each trading Friday, and trading of options are only done at 5-min intervals. Again, these are constraints set by resources rather than practical considerations.

Results could be improved practically if trading is done daily rather than only once per week.
- In this case, risk size hence entry size can be reduced (to minimise slippage) and still attain better returns.
- This assumes trading behaviour does not change significantly from Fridays to non-Friday trading days.

Equity Curve for Friday Tradings
<img src="./attachments/05 walk-fwd full 1.png" width="600"/>

Equity curve shows slow consistent returns for most part. The tail end (final 30 weeks) of the curve experienced some major drawdown, possibly driven by President Trump's frequent and unpredictable policies.

# 06 Results analysis.ipynb

Through the above steps of trading, testing and interpreting the RandomForest-based results, the final strategy used has the following parameters:
```
{
    # used in TA
    "fast": [20, 30], #sma|rsi|macd
    "slow_mult": [3], # sma|rsi|macd, for ATR also
    "rsi_threshold": [70], #rsi only

    # used in trade env
    "opt_leg1_dollar_from_atm" : [2, 5],
    "opt_leg2_dollar_from_leg1" : [5, 10],
    "stoploss_pct_of_maxprofit" : [.1, .5, 1.],
}
```

The over-arching strategy remains unchanged.






## Limitations
1. It is clear that the hypothetical entry sizes intended are large compared to the market liquidity. In this project, I have assumed that the complete position can be entered at the same price. While a more practical approach may be to break the entry down - and enter at several strikes.