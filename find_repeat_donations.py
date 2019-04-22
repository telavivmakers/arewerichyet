#!/usr/bin/env python3

# coding: utf-8

from datetime import timedelta

import pandas as pd


def median_day(s):
    s = pd.to_datetime(sorted(s))
    s = (s - s.min()).to_series().dt.days
    return s.median()


def statistics(debug=False):
    df = pd.read_csv('all.csv')
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    start_of_last_month = df.date.max().replace(day=1)
    prev_30_days = (start_of_last_month - timedelta(days=30))

    df_last_month = df[df['date'] >= start_of_last_month]
    last_month = df_last_month.loc[:, 'date'].min().strftime('%B') # string of month
    df_prev_30_days = df[(df['date'] < start_of_last_month) & (df['date'] >= prev_30_days)]
    prev_month = df_prev_30_days.loc[:, 'date'].min().month

    id_median = df.groupby('id').agg({'date': tuple}).date.apply(median_day)

    maybe_candidates = id_median[(id_median > 10) & (id_median < 40)].index

    not_month_periodic = df[~df.id.isin(maybe_candidates)]

    part_a = df[df.id.isin(maybe_candidates)].dropna(subset=['income'])

    income_vc = part_a.income.value_counts()

    interesting_incomes = income_vc[income_vc > 1].index

    part_b = part_a[part_a.income.isin(interesting_incomes)].sort_values('date')

    c = part_b.groupby(['id', 'income']).date.agg([set, 'count', median_day, 'max'])

    repeaters = c[(c['count'] > 1) & (c['max'].dt.month == 4)]['max'].sort_index()

    def summary(sdf, prefix):
        return {
            f'{prefix} income': sdf.income.sum(),
            f'{prefix} expense': sdf.expense.sum(),
            f'{prefix} net': sdf.income.sum() - sdf.expense.sum(),
        }

    ret = pd.Series(dict(**{
            'Repeating payments (i.e. probably Members)': repeaters.reset_index()['income'].sum(),
            'Repeating payments count (i.e. member number estimate)': repeaters.shape[0],
        },
        **summary(df_last_month, f'{last_month}'),
        **summary(df_prev_30_days, f'[{prev_30_days.date()}..{start_of_last_month.date()})')
    ))
    if debug:
        return ret, df, last_month, prev_30_days
    return ret


if __name__ == '__main__':
    print(statistics())
