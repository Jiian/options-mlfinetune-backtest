import os
from dotenv import load_dotenv
from datetime import datetime
from dateutil.relativedelta import relativedelta

from zoneinfo import ZoneInfo
import io
import requests
import pandas as pd
from eodhd import APIClient

class DataUpdateModule:
    
    def __init__(self, options_interval_minutes = 5):
        # Get tokens
        load_dotenv()
        self.TOKEN_EODHD = os.getenv('TOKEN_EODHD')
        self.TOKEN_ORATS = os.getenv('TOKEN_ORATS')
        self.EODHD_api = self._connect_to_eodhd()

        # params
        self.options_interval_minutes = options_interval_minutes

    def _connect_to_eodhd(self):
        api = APIClient(self.TOKEN_EODHD)
        return api
    
    def _get_stock_data(self, from_est, to_est):
        """ Get intraday historical data for SPY between from_est and to_est (both datetime objects in EST timezone).
        
        Args:
            from_est (datetime): Start datetime in EST timezone.
            to_est (datetime): End datetime in EST timezone (minute-inclusive).
        
        Returns:
            pd.DataFrame: DataFrame containing intraday historical data with datetime in EST timezone.
        """
        # from_utc = (from_est + relativedelta(hours = 5)).replace(tzinfo = pytz.utc)
        # to_utc = (to_est + relativedelta(hours = 5)).replace(tzinfo = pytz.utc)
        df = self.EODHD_api.get_intraday_historical_data(
            symbol = "SPY.US", 
            interval = "1m", 
            from_unix_time = from_est.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(ZoneInfo('UTC')).timestamp(), #from_utc.timestamp(),
            to_unix_time = to_est.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(ZoneInfo('UTC')).timestamp()#to_utc.timestamp()
        )
        df = pd.DataFrame(df)
        df.loc[:, "datetime"] = pd.to_datetime(df.loc[:, "timestamp"], unit='s').dt.tz_localize('UTC').dt.tz_convert('America/New_York') #df.loc[:, "datetime"]) - pd.Timedelta(hours = 5)
        df = df.loc[:, ["datetime", "open", "high", "low", "close", "volume"]].set_index('datetime')
        return df
    
    def _get_options_data(self, trade_minute_est):
        """ Get options data for SPY at the given trade minute in EST timezone.
        
        Args:
            trade_minute_est (datetime): Trade minute in EST timezone (seconds must be zero).
        
        Returns:
            pd.DataFrame: DataFrame containing filtered options data.
        """
        assert trade_minute_est.second == 0, "Seconds must be zero"
        trade_date_str = trade_minute_est.strftime("%Y%m%d%H%M")
        url = "https://api.orats.io/datav2/historical/one-minute/strikes/chain"

        querystring = {"token" : self.TOKEN_ORATS, "ticker" : "SPY", "tradeDate" : trade_date_str}
        response = requests.request("GET", url, params=querystring)
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        if response.status_code == 404:
            return None
        df_out = df[
                (df.loc[:, "dte"] == 1) #&
                # ((df.loc[:, "delta"] > 0.05) | ((df.loc[:, "delta"] - 1).abs() < 0.95)) &
                # ((df.loc[:, "delta"] < 0.95) | ((df.loc[:, "delta"] - 1).abs() > 0.05)) &
                # (df.loc[:, "delta"].abs() < 0.95)
            ].eval("callDelta = delta").eval("putDelta = callDelta - 1").loc[:, [
                "strike", "stockPrice", "callDelta", "putDelta", 'callMidIv', 'putMidIv',
                'callOpenInterest', 'callVolume', 'callBidSize', 'callAskSize', 'callBidPrice', 'callAskPrice',
                'putOpenInterest', 'putVolume', 'putBidSize', 'putAskSize', 'putBidPrice', 'putAskPrice'
            ]].assign(time = trade_minute_est.replace(tzinfo=ZoneInfo("America/New_York")))
        return df_out
    
    def update_data(self, trade_date, update_stock = True, update_options = True):
        df_stock = None
        df_options = None
        
        if update_stock:
            # Update stock data
            df_stock = self._get_stock_data(
                from_est = trade_date.replace(hour = 7, minute = 30, second = 0),
                to_est = trade_date.replace(hour = 15, minute = 0, second = 0)
            )
            print(f"Stock data: {len(df_stock)} rows")
            # Save data
            df_stock.to_csv(f"data/stock_data_{trade_date.strftime('%Y%m%d')}.csv")

        if update_options:
            # Update options data
            start = trade_date.replace(hour = 9, minute = 30, second = 0)
            end = trade_date.replace(hour = 15, minute = 1, second = 0)
            delta = relativedelta(minutes = self.options_interval_minutes)
            dfs = list()
            while start <= end:
                df = self._get_options_data(trade_minute_est = start)
                print("*", end="", flush=True)
                dfs.append(df)
                start += delta
            df_options = pd.concat(dfs, axis=0)
            print(f"\nOptions data: {len(df_options)} rows")
            # Save data
            df_options.to_csv(f"data/options_data_{trade_date.strftime('%Y%m%d')}.csv")

        return df_stock, df_options
    
    def read_data(self, trade_date):
        df_stock = pd.read_csv(f"data/stock_data_{trade_date.strftime('%Y%m%d')}.csv", parse_dates=['datetime'], index_col='datetime')
        df_options = pd.read_csv(f"data/options_data_{trade_date.strftime('%Y%m%d')}.csv", parse_dates=['time']).drop(columns=['Unnamed: 0'])
        return df_stock, df_options