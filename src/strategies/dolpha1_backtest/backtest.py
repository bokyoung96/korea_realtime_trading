import math

from add_key_vars import *


class BacktestBTM(AddKeyVars):
    def __init__(self, 
                 intra_data: pd.DataFrame, 
                 daily_data: pd.DataFrame, 
                 dividends: pd.DataFrame, 
                 rolling_vol: int = 14, 
                 rolling_move: int = 14,
                 AUM: float = 1e8,
                 commission: float = 0.0035,
                 min_comm_per_order: float = 0.35,
                 band_multiplier: int = 1,
                 trade_freq: int = 15,
                 sizing_type: str = 'full_notional',
                 target_vol: float = 0.02,
                 max_leverage: int = 4):
        super().__init__(intra_data, 
                         daily_data, 
                         dividends, 
                         rolling_vol, 
                         rolling_move)
        self.AUM = AUM
        self.commission = commission
        self.min_comm_per_order = min_comm_per_order
        self.band_multiplier = band_multiplier
        self.trade_freq = trade_freq
        self.sizing_type = sizing_type
        self.target_vol = target_vol
        self.max_leverage = max_leverage
        
        self.df = self.run()        
        self.ret, self.trades = self.backtest()
        
    @property
    def temp(self):
        return self.df.groupby('day')
    
    @property
    def res(self):
        if not hasattr(self, '_res'):
            df = pd.DataFrame(index=self.days)
            df['ret'] = np.nan
            df['AUM'] = self.AUM
            df['ret_bm'] = np.nan
            self._res = df
        return self._res
    
    @property
    def daily_data(self):
        df = self.daily_data_.copy()
        df['caldt'] = pd.to_datetime(df['caldt']).dt.date
        df.set_index(['caldt'], inplace=True)
        df['ret'] = df['close'].diff() / df['close'].shift()
        return df
    
    def backtest(self):
        daily_groups = self.df.groupby('day')
        
        trades = []
        for day in range(1, len(self.days)):
            curr_day = self.days[day]
            prev_day = self.days[day - 1]
            
            if prev_day in daily_groups.groups and curr_day in daily_groups.groups:
                prev_day_data = daily_groups.get_group(prev_day)
                curr_day_data = daily_groups.get_group(curr_day)
                
                if 'sigma_open' in curr_day_data.columns and curr_day_data['sigma_open'].isna().all():
                    continue
                
                prev_close_adjusted = prev_day_data['close'].iloc[-1] - self.df.loc[curr_day_data.index, 'dividend'].iloc[-1]
                open_price = curr_day_data['open'].iloc[0]
                curr_close_prices = curr_day_data['close']
                
                d_vol = curr_day_data['d_vol'].iloc[0]
                vwap = curr_day_data['vwap']
                sigma_open = curr_day_data['sigma_open']
                
                UB = max(open_price, prev_close_adjusted) * (1 + self.band_multiplier * sigma_open)
                LB = min(open_price, prev_close_adjusted) * (1 - self.band_multiplier * sigma_open)
                
                signals = np.zeros_like(curr_close_prices)
                signals[(curr_close_prices > UB) & (curr_close_prices > vwap)] = 1
                # signals[(curr_close_prices < LB) & (curr_close_prices < vwap)] = -1
                
                prev_aum = self.res.loc[prev_day, 'AUM']
                if self.sizing_type == "vol_target":
                    if math.isnan(d_vol):
                        shares = round(prev_aum / open_price * self.max_leverage)
                    else:
                        shares = round(prev_aum / open_price * min(self.target_vol / d_vol, self.max_leverage))
                
                elif self.sizing_type == "full_notional":
                    shares = round(prev_aum / open_price)

                trade_indices = np.where(curr_day_data['min_from_open'] % self.trade_freq == 0)[0]
                exposure = np.full(len(curr_day_data), np.nan)
                exposure[trade_indices] = signals[trade_indices]
                
                last_valid = np.nan
                filled_values = []
                for value in exposure:
                    if not np.isnan(value):
                        last_valid = value
                    if last_valid == 0:
                        last_valid = np.nan
                    filled_values.append(last_valid)
                
                exposure = pd.Series(filled_values, 
                                     index = curr_day_data.index).shift(1).fillna(0).values
                trades_count = np.sum(np.abs(np.diff(np.append(exposure, 0))))
                trades.append(trades_count)
                
                chg_1m = curr_close_prices.diff()
                gross_pnl = np.sum(exposure * chg_1m) * shares
                commmission_paid = trades_count * max(self.min_comm_per_order, self.commission * shares)
                net_pnl = gross_pnl - commmission_paid
                ret = net_pnl / prev_aum
                
                self.res.loc[curr_day, 'AUM'] = prev_aum + net_pnl
                self.res.loc[curr_day, 'ret'] = ret
                self.res.loc[curr_day, 'ret_bm'] = self.daily_data.loc[self.daily_data.index == curr_day, 'ret'].values[0]
        trades = pd.DataFrame([np.nan] * self.rolling_move + trades, 
                              columns=['trades'])
        return ret, trades
    

if __name__ == "__main__":
    tkr = 'A233740'
    intra_data = pd.read_pickle(f'./data/{tkr}.pkl')
    daily_data = pd.read_pickle(f'./data/{tkr}_daily.pkl')
    dividends = pd.read_pickle(f'./data/{tkr}_dividends.pkl')
    
    
    cls = BacktestBTM(intra_data=intra_data,
                      daily_data=daily_data,
                      dividends=dividends)
    
    cls.res['AUM'].plot()
    # cls.res.to_excel(f'./results/res_{tkr}_1_15_notional_nodiv_long.xlsx')
