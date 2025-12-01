import numpy as np
import pandas as pd
import sqlite3 as sql


class GetData:
    def __init__(self):
        pass
    
    @property
    def data_path_1(self) -> str:
        return './data/2023-03-31_stock_price(1min).db'
    
    @property
    def data_path_2(self) -> str:
        return './data/2024-05-03_stock_price(1min).db'
    
    def get_tkr(self,
                path: str,
                tkr: str) -> pd.DataFrame:
        conn = sql.connect(path)
        return pd.read_sql("SELECT * FROM " + tkr, con=conn)
    
    def combine_1min_data(self,
                          tkr):
        df1 = self.get_tkr(path=self.data_path_1,
                           tkr=tkr)
        df2 = self.get_tkr(path=self.data_path_2,
                           tkr=tkr)
        
        df1['date'] = pd.to_datetime(df1['date'], format='%Y%m%d%H%M')
        df2['date'] = pd.to_datetime(df2['date'], format='%Y%m%d%H%M')
        
        df = pd.concat([df1, df2]).drop_duplicates(subset='date').sort_values(by='date')
        df.reset_index(drop=True, inplace=True)
        df.rename(columns={'date': 'caldt'}, inplace=True)
        return df
    
    def get_daily_data(self,
                       df: pd.DataFrame):
        """
        df format should be as: self.combine_1min_data(self, tkr)
        """
        df['daily'] =df['caldt'].dt.date
        daily_df = df.groupby('daily').apply(lambda x: pd.Series({
            'open': x.loc[x['caldt'].dt.time == pd.to_datetime('15:30').time(), 'close'].values[0],
            'high': x.loc[x['caldt'].dt.time == pd.to_datetime('15:30').time(), 'close'].values[0],
            'low': x.loc[x['caldt'].dt.time == pd.to_datetime('15:30').time(), 'close'].values[0],
            'close': x.loc[x['caldt'].dt.time == pd.to_datetime('15:30').time(), 'close'].values[0],
            'volume': x['volume'].sum(),
            'caldt': pd.to_datetime(x['daily'].values[0])
            })).reset_index(drop=True)
        return daily_df
    
    def get_daily_ohlcv_data(self,
                             df: pd.DataFrame):
        """
        Return ohlcv data.
        """
        df['daily'] = df['caldt'].dt.date
        daily_df = df.groupby('daily').apply(lambda x: pd.Series({
            'open': x.loc[x['caldt'].dt.time == pd.to_datetime('09:00').time(), 'open'].values[0],
            'high': x['high'].max(),
            'low': x['low'].min(),
            'close': x.loc[x['caldt'].dt.time == pd.to_datetime('15:30').time(), 'close'].values[0],
            'volume': x['volume'].sum(),
            'caldt': pd.to_datetime(x['daily'].values[0])
            })).reset_index(drop=True)
        return daily_df
    
    def get_dividends_data_temp(self,
                                df: pd.DataFrame):
        """
        df format should be as: self.get_daily_data(self, df)
        """
        dividends = pd.DataFrame(df['caldt'])
        dividends['dividend'] = 0
        return dividends
    
    def save_all_as_pkl(self,
                        tkr: str,
                        save: str = 'Y'):
        df_1m = self.combine_1min_data(tkr=tkr)
        df_1d = self.get_daily_data(df=df_1m)
        df_div = self.get_dividends_data_temp(df=df_1d)
        
        if save == 'Y':
            df_1m.to_pickle(f'./data/{tkr}.pkl')
            df_1d.to_pickle(f'./data/{tkr}_daily.pkl')
            df_div.to_pickle(f'./data/{tkr}_dividends.pkl')
        return df_1m, df_1d, df_div


if __name__ == "__main__":
    tkr = 'A379800'
    get_data = GetData()
    get_data.save_all_as_pkl(tkr=tkr, save='Y')