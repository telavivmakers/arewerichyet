#!/bin/env python3
# coding: utf-8
import re
from argparse import ArgumentParser
from pdb import set_trace as b
from os import getcwd, environ
from time import sleep # TODO - remove in favor of better 'wrappers'
from pathlib import Path
from datetime import datetime
from time import time
from io import StringIO
import subprocess
import sys
import base64

import dotenv

from tabulate import tabulate
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

import pydiscourse

from selenium import webdriver
from selenium.webdriver import Firefox, FirefoxProfile
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

from find_repeat_donations import statistics


dotenv.load_dotenv()


assert 'PASSWORD' in environ
assert 'USERNAME' in environ


# seems that HEADLESS does not work right now, somehow fibi recognizes and blocks our login attempt. default to with head
HEADLESS = environ.get('TAMI_HEADLESS', '0')[:1].lower() in {'1', 't'} # False for debugging

if Path('./geckodriver').exists():
    path = environ['PATH']
    cwd = getcwd()
    environ['PATH'] = f'{path}:{cwd}'


def status(txt):
    print(f'{datetime.now()}: {txt}')
    sys.stdout.flush()


def showpng(filename):
    get_ipython().system(f'xdg-open {filename}')


def element_screenshot(e, filename, show=True):
    e.screenshot(filename)
    if show:
        showpng(filename)


def browser_screenshot(browser, filename, show=True):
    browser.get_screenshot_as_file(filename)
    if show:
        showpng(filename)


def warn_if_multiple(items):
    if len(items) > 1:
        print(f'more than one item: {len(items)}')
    if len(items) == 0:
        return None
    return items[0]


def missing(exe):
    try:
        subprocess.check_output(['which', exe])
        return False
    except:
        return True


def assert_have_geckodriver():
    if not missing('geckodriver'):
        return
    print('\nerror: missing geckodriver')
    print('please install by:\nxdg-open https://github.com/mozilla/geckodriver/releases/latest')
    print('unpack to execution directory or to PATH')
    raise SystemExit


def export_fibi_actions_from_last_month(args):
    # if we find a current file, just use it
    here = Path('.').absolute()
    latest_xls = latest_file(list(here.glob('Fibi*.xls')))
    if args.cache or (not args.force and (latest_xls is not None and time() - latest_xls.stat().st_mtime < 3600)):
        status(f'using cached file ({latest_xls})')
        df = fibi_to_dataframe(latest_xls)
    else:
        assert_have_geckodriver()
        df = export_fibi_actions_from_last_month_helper(downloaddir=str(here), headless=HEADLESS, verbose=args.verbose)
    today = datetime.now().date()
    today_str = today.strftime('%Y%m%d')
    df.to_csv(f'fibi_last_month_export_{today_str}.csv', index=False)
    return df


def export_fibi_actions_from_last_month_helper(downloaddir, headless=True, verbose=False):
    opts = Options()

    opts.headless = headless
    assert opts.headless == headless

    if not headless:
        print("will create a window (needs a working X11 server). DISPLAY = {environ.get('DISPLAY', None)}")

    profile = FirefoxProfile()
    profile.set_preference("browser.download.panel.shown", False)
    profile.set_preference("browser.helperApps.neverAsk.openFile","text/csv,application/vnd.ms-excel")
    profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/vnd.ms-excel")
    profile.set_preference("browser.download.folderList", 2)
    profile.set_preference("browser.download.dir", downloaddir)

    # error seen when running under systemd, directly or via tmux
    # Unable to find a matching set of capabilities
    capabilities = webdriver.DesiredCapabilities.FIREFOX
    #capabilities["marionett"] = False

    status('creating selenium driver')
    service_args = ['-vv'] if verbose else []
    browser = Firefox(
        options=opts,
        firefox_profile=profile,
        capabilities=capabilities,
        service_args=service_args,
        firefox_binary=FirefoxBinary('/usr/bin/firefox'),
    )

    status('getting fibi login page')
    browser.get('https://www.fibi.co.il/wps/portal/FibiMenu/Marketing/Platinum')
    login_trigger = browser.find_element_by_class_name("login-trigger")
    login_trigger.click()
    #login_trigger.is_displayed()
    #ps = browser.page_source
    #browser.find_element_by_id('loginFrame')
    #browser.switch_to.parent_frame()
    browser.switch_to.frame('loginFrame')
    username = WebDriverWait(browser, 20).\
            until(EC.presence_of_element_located((By.ID, 'username')))
    password = browser.find_element_by_id('password')

    submit_button = WebDriverWait(browser, 20).\
            until(EC.presence_of_element_located((By.ID, 'continueBtn')))

    username.send_keys(environ['USERNAME'])
    password.send_keys(environ['PASSWORD'])

    element_screenshot(username, 'username_after_send_keys.png', show=False)
    element_screenshot(password, 'password_after_send_keys.png', show=False)
    #browser.find_elements_by_class_name('btn')[0].location
    #browser.find_elements_by_class_name('login')
    #browser.log_types
    #password.send_keys(Keys.ENTER)
    #password.send_keys(Keys.RETURN) # killed firefox
    status('logging in')
    #username.submit() # or password.submit()
    browser_screenshot(browser, 'before_password_submit.png', show=False)
    sleep(0.5)
    submit_button.click()
    browser_screenshot(browser, 'after_password_submit.png', show=False)
    browser.switch_to.default_content() # otherwise you get 'can't access dead object' - we need to switch back from the iframe
    status('waiting for tnuot')
    tnuot = WebDriverWait(browser, 20).\
            until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, 'תנועות בחשבון')))
    browser_screenshot(browser, 'after_password_and_some_seconds.png', show=False)

    def repeat_click_until_no_intercept(e):
        for repeat in range(10):
            try:
                e.click()
                print()
                return
            except selenium.common.exceptions.ElementClickInterceptedException:
                print('.', end=None)
                sleep(5)
        print(f'timeout waiting for element to not be intercepted for clicking: {e}')
        raise SystemExit

    repeat_click_until_no_intercept(tnuot)
    prev_month = WebDriverWait(browser, 20).\
            until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, 'תנועות מתחילת חודש נוכחי')))
    prev_month.click()
    export_to_excel = WebDriverWait(browser, 20).\
            until(EC.presence_of_element_located((By.CLASS_NAME, 'excell')))
    status('downloading csv from previous month until now')
    export_to_excel.click()
    sleep(2) # not always seeing csv file created. should be another way to query webdriver for saved file, or inotify on dir
    fibis = list(Path('.').glob('Fibi*.xls'))
    latest = latest_file(fibis)
    if latest is None:
        status('no file returned; try later - seen error during middle of the night')
        raise SystemExit
    return fibi_to_dataframe(latest)


def latest_file(paths):
    if len(paths) == 0:
        return None
    return sorted([(x.stat().st_ctime, x) for x in paths])[-1][1]


def fibi_to_dataframe(filename):
    latest_df = pd.read_excel(filename, header=1, usecols=[1, 2, 3, 4, 5, 6, 7, 8])
    date_col = warn_if_multiple([x for x in latest_df.columns if 'תאריך' in x and 'תאריך ערך' not in x])
    latest_df = latest_df.rename(columns={date_col: 'date', 'סוג פעולה': 'op_type', 'תיאור': 'description', 'אסמכתא': 'id', 'זכות': 'income', 'חובה': 'expense', 'תאריך ערך': 'value_date', 'יתרה': 'balance'})
    def clean(s):
        return s.replace(' ', '')
    latest_df.date = pd.to_datetime(clean(latest_df.date))
    latest_df.value_date = pd.to_datetime(clean(latest_df.value_date))
    for col in ['balance', 'income', 'expense']:
        latest_df[col] = pd.to_numeric(clean(latest_df[col]), errors='coerce')
    return latest_df


dc_username = environ['DISCOURSE_API_USERNAME']
dc_title = 'bank status - automatically generated'



class BalanceDiscourse:
    def __init__(self):
        client = pydiscourse.client.DiscourseClient(
            host='https://discourse.telavivmakers.org',
            api_key=environ['DISCOURSE_API_KEY'],
            api_username=dc_username)
        self.client = client
        category_name = 'Staying Alive'
        client_categories = client.categories()
        finance_category = warn_if_multiple([x for x in client_categories if x['name'] == category_name])
        self.category_id = category_id = finance_category['id']
        user_topics = client.topics_by(dc_username)
        topic_title_to_id = {x['title'].lower(): x['id'] for x in user_topics}
        self.topic_id = topic_title_to_id.get(dc_title.lower())

    def get_last_posted_balance(self):
        # find last post that was posted automatically
        post_id = None
        balance = None
        posts = self.client.posts(self.topic_id)['post_stream']['posts']
        if len(posts) > 0:
            post = posts[0]
            cooked = post['cooked']
            post_id = post['id']
            match = re.search('balance from [0-9][0-9][0-9][0-9]-[0-9][0-9]*-[0-9][0-9]*: ([0-9]*.[0-9]*)', cooked)
            if match:
                balance = float(match.groups()[0])
        return post_id, balance

    def post(self, date, balance, post_id, latest, really):
        latest = tabulate(latest.values, latest.columns, 'github') if latest is not None else 'latest - to redo with excel (alon)'
        b64_plots = get_balance_plots()
        images = '\n'.join([
            f'''<img src="data:image/png;base64,{b64}" alt="{name} (date)" />'''
            for name, b64 in b64_plots.items()])
        stats = statistics()
        content = f'''balance from {date}: {balance}

{latest}

{images}

{stats.to_string(dtype=False)}

------

This topic is updated automatically.

Please avoid replying here if possible.

Repository producing this:

https://github.com/telavivmakers/arewerichyet.git
'''
        if not really:
            with open('test_post.md', 'w+') as fd:
                fd.write(content)
            size = Path('test_post.md').stat().st_size
            print(f'not posting, wrote test_post.md with {size} bytes')
            return
        if post_id is None:
            self.client.create_post(content=content, title=dc_title, category_id=self.category_id, topic_id=self.topic_id)
        else:
            self.client.update_post(post_id=post_id, content=content, reason='automatic update from source of truth')


def df_to_discourse(df, latest, really=False, force=False):
    status('getting last post')
    client = BalanceDiscourse()
    balance = df.iloc[-1].balance
    last_balance_post_id, last_balance = client.get_last_posted_balance()
    if last_balance == balance and not force:
        status('no change, not posting')
    else:
        date = datetime.now().date() # This is the last date from the bank, but we are using the date we got this from the bank; df.iloc[-1].date.date()
        client.post(date=date, balance=balance, post_id=last_balance_post_id, latest=latest, really=really)
    status('done')


def fig_to_file_and_b64(fig, filename):
    fig.savefig(filename)
    with open(filename, 'rb') as fd:
        b = fd.read()
    return base64.b64encode(b).decode()


def get_balance_plots():
    df = pd.read_csv('all.csv')[['date', 'balance']].dropna()
    df['date'] = pd.to_datetime(df['date'])
    df['balance'] = pd.to_numeric(df['balance'])
    fig, ax = plt.subplots()
    sns.scatterplot(x=df['date'].dt.day, y=df['balance'], hue=df['date'].dt.month, ax=ax)
    plots = {
        'per day': fig_to_file_and_b64(fig, 'all_balance_per_day.png')
    }
    fig, ax = plt.subplots()
    ax.plot(df['date'], df['balance'], '.')
    fig.autofmt_xdate(rotation=45)
    plots['all'] =  fig_to_file_and_b64(fig, 'all_balance.png')
    return plots


def get_latest():
    """
    # WIP - into python
    files = subprocess.check_output(['find', '.', '-maxdepth', '1', '-ctime', '-14', '-iname', 'FibiSave*.xls']).decode().split('\n')
    dfs = [fibi_to_dataframe(f) for f in files if f.strip() != '']
    df = pd.concat(dfs, sort=True).drop_duplicates()
    df.to_csv('all.csv')
    df[['expense', 'value_date']]
    b()
    """
    # implemented with an xsv script right now, just use that
    if missing('xsv'):
        if missing('cargo'):
            print("install rust :\ncurl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
        if missing('xsv'):
            print('please install xsv: \ncargo install xsv')
        raise SystemExit
    s = StringIO(subprocess.check_output('./last_files_expenses.sh').decode())
    df = pd.read_csv(s)
    df['description'] = df.apply(lambda row: pd.isna(row.recurring) and row.one_time or row.recurring, axis=1)
    df = df.drop(columns=['recurring', 'one_time'])
    return df


def main():
    parser = ArgumentParser()
    parser.add_argument('--no-cache', action='store_false', dest='cache', default=True)
    parser.add_argument('--really', action='store_true', default=False)
    parser.add_argument('--force', action='store_true', default=False)
    parser.add_argument('--force-fetch', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    args = parser.parse_args()
    df = export_fibi_actions_from_last_month(args)
    latest = get_latest()
    df_to_discourse(df, really=args.really, force=args.force, latest=latest)


if __name__ == '__main__':
    main()
    #discourse_test()
