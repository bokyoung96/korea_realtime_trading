import numpy as np
import pandas as pd


class AddKeyVars:
    def __init__(self, intra_data: pd.DataFrame, daily_data: pd.DataFrame, dividends: pd.DataFrame, rolling_vol: int = 14, rolling_move: int = 14):
        self.intra_data_ = intra_data.copy()
        self.daily_data_ = daily_data.copy()
        self.dividends_ = dividends.copy()
        
        self.rolling_vol = rolling_vol
        self.rolling_move = rolling_move
        
        self.intra_data_['day'] = pd.to_datetime(self.intra_data_['caldt']).dt.date
        self.intra_data_.set_index(['caldt'], inplace=True)
        
        self.intra_data_['move_open'] = np.nan
        self.intra_data_['vwap'] = np.nan
        self.intra_data_['d_vol'] = np.nan

    @property
    def intra_data(self):
        return self.intra_data_

    @property
    def days(self):
        return self.intra_data_['day'].unique()

    @property
    def d_ret(self):
        return pd.Series(index=self.days, dtype=float)
    
    @staticmethod
    def calculate_vwap(curr_day_data):
        hlc = (curr_day_data['high'] + curr_day_data['low'] + curr_day_data['close']) / 3
        vol_hlc = curr_day_data['volume'] * hlc
        cum_vol_hlc = vol_hlc.cumsum()
        cum_vol = curr_day_data['volume'].cumsum()
        return cum_vol_hlc / cum_vol

    @staticmethod
    def calculate_move_open(curr_day_data, open_price):
        return (curr_day_data['close'] / open_price - 1).abs()

    @staticmethod
    def calculate_volatility(d_ret, curr_day, prev_day, rolling_vol):
        return d_ret.loc[prev_day:curr_day].iloc[-rolling_vol:].std(skipna=False)

    def apply_move_metrics(self):
        daily_groups = self.intra_data.groupby('day')
        d_ret = self.d_ret.copy()

        for day in range(1, len(self.days)):
            curr_day = self.days[day]
            prev_day = self.days[day - 1]

            curr_day_data = daily_groups.get_group(curr_day)
            prev_day_data = daily_groups.get_group(prev_day)

            # VWAP
            self.intra_data_.loc[curr_day_data.index, 'vwap'] = self.calculate_vwap(curr_day_data)

            # MOVE
            open_price = curr_day_data['open'].iloc[0]
            self.intra_data_.loc[curr_day_data.index, 'move_open'] = self.calculate_move_open(curr_day_data, open_price)

            # VOLATILITY
            d_ret.loc[curr_day] = curr_day_data['close'].iloc[-1] / prev_day_data['close'].iloc[-1] - 1
            if day >= self.rolling_vol:
                self.intra_data_.loc[curr_day_data.index, 'd_vol'] = self.calculate_volatility(d_ret, curr_day, prev_day, self.rolling_vol)

    def apply_time_metrics(self):
        self.intra_data_['min_from_open'] = ((self.intra_data_.index - self.intra_data_.index.normalize()) / pd.Timedelta(minutes=1)) - 9 * 60
        self.intra_data_['min_of_day'] = self.intra_data_['min_from_open'].round().astype(int)
        minute_groups = self.intra_data_.groupby('min_of_day')

        self.intra_data_['move_open_rolling_mean'] = minute_groups['move_open'].transform(
            lambda x: x.rolling(window=self.rolling_move, min_periods=self.rolling_move - 1).mean()
        )
        self.intra_data_['sigma_open'] = minute_groups['move_open_rolling_mean'].transform(lambda x: x.shift(1))

    def merge_dividends(self):
        self.dividends_['day'] = pd.to_datetime(self.dividends_['caldt']).dt.date
        self.intra_data_ = self.intra_data_.merge(self.dividends_[['day', 'dividend']], on='day', how='left')
        self.intra_data_['dividend'] = self.intra_data_['dividend'].fillna(0)

    def run(self):
        self.apply_move_metrics()
        self.apply_time_metrics()
        self.merge_dividends()
        return self.intra_data_


# if __name__ == "__main__":
#     intra_data = pd.read_pickle('./data/233740.pkl')
#     daily_data = pd.read_pickle('./data/233740_daily.pkl')
#     dividends = pd.read_pickle('./data/233740_dividends.pkl')

#     cls = AddKeyVars(intra_data=intra_data, 
#                      daily_data=daily_data, 
#                      dividends=dividends)
#     result = cls.run()
