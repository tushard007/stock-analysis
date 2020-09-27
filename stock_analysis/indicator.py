import yfinance as yf
import multiprocessing
import os
import yaml
import datetime
import dateutil
import pandas as pd
from stock_analysis.utils.logger import logger
from stock_analysis.data_retrive import DataRetrive
from typing import Dict, List, Tuple, Union
now_strting = datetime.datetime.now().strftime('%d-%m-%Y')

yf.pdr_override()
logger = logger()
pd.options.display.float_format = '{:,.2f}'.format


class Indicator:
    """Perform all variety of Indicator operation
    """

    def __init__(self, path: str = None, company_name: List = None):
        """
        Parameters
        ----------
        path : str, optional
            Path to company yaml/json. Either path or company_name
            can be used, by default None
        company_name : List, optional
            List of company name. If path is used then this is obsolete
             as 'path' preside over 'company_name', by default None
        """

        self.path = path
        self.company_name = company_name

        if path is not None:
            if 'yaml' in os.path.split(self.path)[-1]:
                with open(self.path, 'r') as f:
                    self.data = yaml.load(f, Loader=yaml.FullLoader)
        else:
            self.data = {'company': self.company_name}

    def volume_indicator_n_days(self, duration: int = 90,
                                save: bool = True,
                                export_path: str = '.',
                                verbosity: int = 1) -> pd.DataFrame:
        """Mean Volume Indicator based on desired days

        Parameters
        ----------
        duration : int, optional
            Total days from current date to retrive data, by default 90
        save : bool, optional
            Save to hard disk, by default True
        export_path : str, optional
            Path to save, to be used only if 'save' is true, by default '.'
        verbosity : int, optional
            Level of detail logging,1=< Deatil, 0=Less detail , by default 1

        Returns
        -------
        pd.DataFrame
            All Volume based indicator
        """
        with multiprocessing.Pool(multiprocessing.cpu_count() - 1) as pool:
            result = pool.starmap(self._parallel_vol_indicator_n_days,
                                  [(company, duration) for company in self.data['company']])

        vol_ind_df = pd.DataFrame(result)
        if verbosity > 0:
            logger.debug(
                f"Here are sample 5 company\n{vol_ind_df.head()}")
        if save is True:
            vol_ind_df.to_csv(
                f"{export_path}/VolumeIndicator90Days_detailed_{now_strting}.csv",
                index=False)
            if verbosity > 0:
                logger.debug(
                    f"Save at {export_path}/VolumeIndicator90Days_detailed_{now_strting}.csv")
        else:
            return vol_ind_df

    def ema_indicator(self, ema_canditate: Tuple[int, int] = (50, 200),
                      cutoff_date: Union[str, datetime.datetime] = 'today',
                      save: bool = True,
                      export_path: str = '.',
                      verbosity: int = 1) -> pd.DataFrame:
        """Exponential moving average based on desired two period (or no of days)

        Parameters
        ----------
        ema_canditate : Tuple[int, int], optional
            [description], by default (50, 200)
        cutoff_date : Union[str,datetime.datetime], optional
            Desired date till which to calculate ema. 'today' for current day,
            eg 01/01/2020 for any other date, by default 'today'
        save : bool, optional
            Save to hard disk, by default True
        export_path : str, optional
            Path to save, to be used only if 'save' is true, by default '.'
        verbosity : int, optional
            Level of detail logging,1=< Deatil, 0=Less detail , by default 1

        Returns
        -------
        -> pd.DataFrame
            EMA and indicators based on it
        """

        with multiprocessing.Pool(multiprocessing.cpu_count() - 1) as pool:
            result = pool.starmap(self._parallel_ema_indicator,
                                  [(company, ema_canditate, cutoff_date, verbosity) for company in self.data['company']])
        ema_indicator_df = pd.DataFrame(result)
        ema_indicator_df.dropna(inplace=True)
        ema_indicator_df['percentage_diff'] = ema_indicator_df.apply(
            lambda x: self._percentage_diff_analysis(
                x[f'ema{str(ema_canditate[0])}'],
                x[f'ema{str(ema_canditate[1])}']),
            axis=1
        )
        ema_indicator_df['outcome'] = ema_indicator_df.apply(
            lambda x: self._outcome_analysis(x['percentage_diff']),
            axis=1
        )

        ema_indicator_df = ema_indicator_df[['company', 'ema_date',
                                             f'ema{str(ema_canditate[0])}',
                                             f'ema{str(ema_canditate[1])}',
                                             'percentage_diff',
                                             'outcome', 'action']]

        if verbosity > 0:
            logger.debug(
                f"Here are sample 5 company\n{ema_indicator_df.head()}")
        if save is True:
            ema_indicator_df.to_csv(
                f"{export_path}/ema_indicator{str(ema_canditate[0])}-{str(ema_canditate[1])}_{len(self.data['company'])}company_{now_strting}.csv",
                index=False)
            if verbosity > 0:
                logger.debug(
                    f"Exported at {export_path}/ema_indicator{str(ema_canditate[0])}-{str(ema_canditate[1])}_{len(self.data['company'])}company_{now_strting}.csv")

        else:
            return ema_indicator_df

    def ema_indicator_detail(self,
                             ema_canditate: Tuple[int, int] = (50, 200),
                             save: bool = True,
                             export_path: str = '.',
                             verbosity: int = 1) -> pd.DataFrame:
        """EMA indicator with detail or wide variety of indicators

        Parameters
        ----------
        ema_canditate : Tuple[int, int], optional
            Period (or days) to calculate EMA, by default (50, 200)
        save : bool, optional
            Save to hard disk, by default True
        export_path : str, optional
            Path to save, to be used only if 'save' is true, by default '.'
        verbosity : int, optional
            Level of detail logging,1=< Deatil, 0=Less detail , by default 1

        Returns
        -------
        pd.DataFrame
        """

        logger.info("Performing EMA Indicator Task")
        ema_short = self.ema_indicator(
            ema_canditate=ema_canditate,
            save=False,
            verbosity=verbosity
        )

        logger.info("Extarcting detail company quote data")
        batch_company_quote = pd.DataFrame()
        with multiprocessing.Pool(multiprocessing.cpu_count() - 1) as pool:
            company_quote = pool.map(
                self._parallel_quote_retrive, ema_short['company'])
        for single_company_quote in company_quote:
            batch_company_quote = batch_company_quote.append(
                single_company_quote)

        batch_company_quote = batch_company_quote.reset_index().rename(columns={
            'index': 'company'})
        batch_company_quote = batch_company_quote[
            ['company', 'longName', 'price', 'regularMarketVolume',
             'marketCap', 'bookValue', 'priceToBook',
             'averageDailyVolume3Month', 'averageDailyVolume10Day',
             'fiftyTwoWeekLowChange', 'fiftyTwoWeekLowChangePercent',
             'fiftyTwoWeekRange', 'fiftyTwoWeekHighChange',
             'fiftyTwoWeekHighChangePercent', 'fiftyTwoWeekLow',
             'fiftyTwoWeekHigh']
        ]

        batch_company_quote['company'] = batch_company_quote['company'].str.replace('.NS', '')

        ema_quote = ema_short.merge(
            batch_company_quote,
            on='company',
            validate='1:1'
        )

        if verbosity > 0:
            logger.debug(
                f"Here are sample 5 company\n{ema_quote.head()}")
        if save is not False:
            ema_quote.to_csv(
                f"{export_path}/ema_indicator_detail{str(ema_canditate[0])}-{str(ema_canditate[1])}_{len(self.data['company'])}company_{now_strting}.csv",
                index=False)
            if verbosity > 0:
                logger.debug(
                    f"Exported at {export_path}/ema_indicator_detail{str(ema_canditate[0])}-{str(ema_canditate[1])}_{len(self.data['company'])}company_{now_strting}.csv")

        else:
            return ema_quote

    def ema_crossover_indicator_detail(self,
                                       ema_canditate: Tuple[int, int, int] = (5, 13, 26),
                                       save: bool = True,
                                       export_path: str = '.',
                                       verbosity: int = 1) -> pd.DataFrame:
        """Exponential moving average for crossover triple period technique

        Parameters
        ----------
        ema_canditate : Tuple[int, int, int], optional
            Three Period (or days) to calculate EMA, by default (5,13,26)
        save : bool, optional
            Save to hard disk, by default True
        export_path : str, optional
            Path to save, to be used only if 'save' is true, by default '.'
        verbosity : int, optional
            Level of detail logging,1=< Deatil, 0=Less detail , by default 1

        Returns
        -------
        pd.DataFrame

        """

        logger.info("Performing EMA Indicator Task")
        ema_short = self._ema_indicator_n3(
            ema_canditate=ema_canditate,
            verbosity=verbosity
        )

        logger.info("Extarcting detail company quote data")
        batch_company_quote = pd.DataFrame()
        with multiprocessing.Pool(multiprocessing.cpu_count() - 1) as pool:
            company_quote = pool.map(
                self._parallel_quote_retrive, ema_short['company'])
        for single_company_quote in company_quote:
            batch_company_quote = batch_company_quote.append(
                single_company_quote)

        batch_company_quote = batch_company_quote.reset_index().rename(columns={
            'index': 'company'})
        batch_company_quote = batch_company_quote[
            ['company', 'longName', 'price', 'regularMarketVolume',
             'marketCap', 'bookValue', 'priceToBook',
             'averageDailyVolume3Month', 'averageDailyVolume10Day',
             'fiftyTwoWeekLowChange', 'fiftyTwoWeekLowChangePercent',
             'fiftyTwoWeekRange', 'fiftyTwoWeekHighChange',
             'fiftyTwoWeekHighChangePercent', 'fiftyTwoWeekLow',
             'fiftyTwoWeekHigh']
        ]

        batch_company_quote['company'] = batch_company_quote['company'].str.replace('.NS', '')

        ema_quote = ema_short.merge(
            batch_company_quote,
            on='company',
            validate='1:1'
        )

        if verbosity > 0:
            logger.debug(
                f"Here are sample 5 company\n{ema_quote.head()}")
        if save is not False:
            ema_quote.to_csv(
                f"{export_path}/ema_indicator_detail{str(ema_canditate[0])}-{str(ema_canditate[1])}_{len(self.data['company'])}company_{now_strting}.csv",
                index=False)
            if verbosity > 0:
                logger.debug(
                    f"Exported at {export_path}/ema_indicator_detail{str(ema_canditate[0])}-{str(ema_canditate[1])}_{len(self.data['company'])}company_{now_strting}.csv")

        else:
            return ema_quote

    def _ema_indicator_n3(self, ema_canditate: Tuple[int, int] = (5, 13, 26),
                         cutoff_date: Union[str, datetime.datetime] = 'today',
                          verbosity: int = 1):

        with multiprocessing.Pool(multiprocessing.cpu_count() - 1) as pool:
            result = pool.starmap(self._parallel_ema_indicator_n3,
                                  [(company, ema_canditate, cutoff_date, verbosity) for company in self.data['company']])
        ema_indicator_df = pd.DataFrame(result)
        ema_indicator_df.dropna(inplace=True)

        if verbosity > 0:
            logger.debug(
                f"Here are sample 5 company\n{ema_indicator_df.head()}")
        return ema_indicator_df

    def _exponential_moving_avarage(self,
                                    data_df: Union[pd.Series, List],
                                    period: int,
                                    cutoff_date: Union[str, datetime.datetime] = 'today',
                                    smoothing_factor: int = 2,
                                    verbosity: int = 1) -> float:
        """Calculate exponential moving avarage based on given period

        Parameters
        ----------
        data : Union[pd.Series,List]
            Data to calculate ema
        period : int
            Period for which ema has to be calculated
        smoothing_factor : int, optional
            Smoothing factor which will be used to calculate
            Multiplying factor, by default 2

        Returns
        -------
        float
            ema value
        """
        ema_list = []
        # Calculating multiplying factor
        mf = smoothing_factor/(1 + period)

        # Calculating first SMA
        sma0 = (sum(data_df['Close'][:period])) / period

        # Calculating first EMA
        ema0 = (data_df['Close'][period] * mf) + (sma0 * (1 - mf))

        # Calculating latest EMA
        ema_pre = ema0

        for idx in range(1, len(data_df)-50):
            ema = (data_df['Close'][idx + 50] * mf) + (ema_pre * (1 - mf))
            ema_pre = ema
            ema_list.append(ema)
            # if cutoff_date is not None:
            if idx == (len(data_df) - 50):
                break
        data_df['ema'] = [pd.NA] * (len(data_df) - len(ema_list)) + ema_list
        if cutoff_date == 'today':
            date = data_df.index[-1]
        else:
            date = self._get_appropriate_date(
                company_df=data_df,
                desired_date=cutoff_date,
                verbosity=verbosity
            )

        return float(data_df[data_df.index == date]['ema'])

    def _get_appropriate_date(self,
                              company_df: pd.DataFrame,
                              desired_date: datetime.datetime,
                              verbosity: int = 1) -> Tuple[datetime.datetime, float]:
        """
        Return appropriate date which is present in data record.

        Parameters
        ----------
        company_df : pd.DataFrame
            Company dataframe
        duration : datetime.datetime
            Desired date cut-off to calculate ema
        verbosity : int, optional
            Level of detail logging, by default 1

        Returns
        -------
        Tuple[datetime.datetime,float]
            Date,Close value on date retrived

        Raises
        ------
        ValueError
            If desired old is older than first record
        """
        if desired_date < company_df.index[0]:
            logger.error(
                f"Given desired date {desired_date.strftime('%d-%m-%Y')} is older than first recorded date {company_df.index[0].strftime('%d-%m-%Y')}")

        if verbosity > 0:
            logger.debug(
                f"Your desired EMA cut-off date is {desired_date.strftime('%d-%m-%Y')}")

        for day_idx in range(1, 100):
            if desired_date not in company_df.index:
                date = desired_date - \
                    dateutil.relativedelta.relativedelta(days=day_idx)
            else:
                date = desired_date
            if date in company_df.index:
                break
        if verbosity > 0 and desired_date != date:
            logger.warning(
                f"Desired date: {desired_date.strftime('%d-%m-%Y')} not found going for next possible date: {date.strftime('%d-%m-%Y')}")

        return date

    def _percentage_diff_analysis(self,
                                  ema_a,
                                  ema_b):
        """
        Used to calculate Percentage difference
        """
        return abs((ema_b - ema_a)/((ema_a + ema_b) / 2) * 100)

    def _outcome_analysis(self, percentage_diff):
        if 5 < percentage_diff < 5:
            outcome = 'close by'
        else:
            outcome = 'far away'
        return outcome

    # TODO: Add all parallel executor function here
    def _parallel_vol_indicator_n_days(self,
                                       company: str = None,
                                       duration: int = 90):
        end = datetime.datetime.now()
        start = end - dateutil.relativedelta.relativedelta(days=duration)
        logger.info(
            f"Retriving data for {company}")
        company_df = DataRetrive.single_company_specific(
            company_name=f"{company}.NS",
            start_date=start,
            end_date=end
        )

        buy_stock = company_df.iloc[-1].Volume > company_df['Volume'].mean()
        print(f"Problem with {company}, moving on")
        return {'company': company,
                'current date': company_df.index[-1].strftime('%d-%m-%Y'),
                'start date': company_df.index[0].strftime('%d-%m-%Y'),
                'current volume': company_df.iloc[-1].Volume,
                'mean volume': company_df['Volume'].mean(),
                'close price': company_df.iloc[-1].Close,
                'action': buy_stock}

    def _parallel_ema_indicator(self,
                                company: str = None,
                                ema_canditate: Tuple[int, int] = (50, 200),
                                cutoff_date: Union[str, datetime.datetime] = 'today',
                                verbosity: int = 1) -> Dict:
        logger.info(
            f"Retriving data for {company}")
        company_df = DataRetrive.single_company_complete(
            company_name=f"{company}.NS")
        if company_df['Close'].isnull().sum() != 0:
            logger.warning(f"{company} have some missing value, fixing it")
            company_df.dropna(inplace=True)
        try:
            EMA_A = self._exponential_moving_avarage(
                data_df=company_df,
                cutoff_date=cutoff_date,
                period=ema_canditate[0],
                verbosity=verbosity
            )
            EMA_B = self._exponential_moving_avarage(
                data_df=company_df,
                cutoff_date=cutoff_date,
                period=ema_canditate[1],
                verbosity=verbosity
            )
            if EMA_A > EMA_B:
                action = 'buy'
            else:
                action = 'sell'
        except (KeyError, IndexError, ValueError):
            logger.warning(
                f"{company} has less record than minimum rexquired")
            EMA_A, EMA_B, action = pd.NA, pd.NA, pd.NA
        return {'company': company,
                'ema_date': now_strting if cutoff_date == 'today' else cutoff_date.strftime('%d-%m-%Y'),
                f'ema{str(ema_canditate[0])}': EMA_A,
                f'ema{str(ema_canditate[1])}': EMA_B,
                'action': action}

    def _parallel_quote_retrive(self, company: str) -> pd.DataFrame:
        logger.info(
            f"Retriving Detail Quote data for {company}")
        return DataRetrive.single_company_quote(f'{company}.NS')

    def _parallel_ema_indicator_n3(self, company: str,
                                   ema_canditate: Tuple[int, int] = (5, 13, 26),
                                   cutoff_date: Union[str, datetime.datetime] = 'today',
                                   verbosity: int = 1):
        logger.info(f"Retriving data for {company}")
        company_df = DataRetrive.single_company_complete(
            company_name=f"{company}.NS")
        if company_df['Close'].isnull().sum() != 0:
            logger.warning(f"{company} have some missing value, fixing it")
            company_df.dropna(inplace=True)
        try:
            EMA_A = self._exponential_moving_avarage(
                data_df=company_df,
                cutoff_date=cutoff_date,
                period=ema_canditate[0],
                verbosity=verbosity
            )
            EMA_B = self._exponential_moving_avarage(
                data_df=company_df,
                cutoff_date=cutoff_date,
                period=ema_canditate[1],
                verbosity=verbosity
            )
            EMA_C = self._exponential_moving_avarage(
                data_df=company_df,
                cutoff_date=cutoff_date,
                period=ema_canditate[2],
                verbosity=verbosity
            )

            percentage_diff_cb = self._percentage_diff_analysis(EMA_C, EMA_B)
            percentage_diff_ca = self._percentage_diff_analysis(EMA_C, EMA_A)
            percentage_diff_ba = self._percentage_diff_analysis(EMA_B, EMA_A)

            if (percentage_diff_cb < 1) and (percentage_diff_ca < 1) and (percentage_diff_ba < 1):
                action = 'buy'
            else:
                action = 'sell'

        except (KeyError, IndexError, ValueError):
            logger.warning(
                f"{company} has less record than minimum required")

            EMA_A, EMA_B, EMA_C, action = pd.NA, pd.NA, pd.NA, pd.NA

        return {'company': company,
                'ema_date': now_strting if cutoff_date == 'today' else cutoff_date.strftime('%d-%m-%Y'),
                f'ema{str(ema_canditate[0])}': EMA_A,
                f'ema{str(ema_canditate[1])}': EMA_B,
                f'ema{str(ema_canditate[2])}': EMA_C,
                # 'percentage_diffCB': percentage_diff_cb,
                # 'percentage_diffCA': percentage_diff_ca,
                # 'percentage_diffBA': percentage_diff_ba,
                'action': action}
