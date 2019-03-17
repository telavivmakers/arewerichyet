#!/bin/env python3
# coding: utf-8
from os import getcwd, environ
from time import sleep # TODO - remove in favor of better 'wrappers'
from pathlib import Path
from datetime import datetime
from time import time

import dotenv

import pandas as pd

import pydiscourse

from selenium import webdriver
from selenium.webdriver import Firefox, FirefoxProfile
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


dotenv.load_dotenv()


HEADLESS = True # False for debugging


def status(txt):
    print(f'{datetime.now()}: {txt}')


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


def export_fibi_actions_from_last_month():
    # if we find a current file, just use it
    here = Path('.').absolute()
    latest_csv = latest_file(list(here.glob('Fibi*.csv')))
    if latest_csv is not None and time() - latest_csv.stat().st_ctime < 3600:
        status('using cached file')
        df = fibi_to_dataframe(latest_csv)
    else:
        df = export_fibi_actions_from_last_month_helper(downloaddir=str(here), headless=HEADLESS)
    today = datetime.now().date()
    today_str = today.strftime('%Y%m%d')
    df.to_csv(f'fibi_last_month_export_{today_str}.csv', index=False)
    return df


def export_fibi_actions_from_last_month_helper(downloaddir, headless=True):
    opts = Options()

    opts.headless = headless
    assert opts.headless == headless

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
    if False:
        service_args = ['-vv']
    else:
        service_args = []
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
    username.submit() # or password.submit()
    browser_screenshot(browser, 'after_password_submit.png', show=False)
    browser.switch_to.default_content() # otherwise you get 'can't access dead object' - we need to switch back from the iframe
    tnuot = WebDriverWait(browser, 20).\
            until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, 'תנועות בחשבון')))
    browser_screenshot(browser, 'after_password_and_some_seconds.png', show=False)

    tnuot.click()
    prev_month = WebDriverWait(browser, 20).\
            until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, 'תנועות מתחילת חודש נוכחי')))
    prev_month.click()
    export_to_excel = WebDriverWait(browser, 20).\
            until(EC.presence_of_element_located((By.CLASS_NAME, 'excell')))
    status('downloading csv from previous month until now')
    export_to_excel.click()
    sleep(2) # not always seeing csv file created. should be another way to query webdriver for saved file, or inotify on dir
    fibis = list(Path('.').glob('Fibi*.csv'))
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
    latest_df = pd.read_csv(filename, encoding='iso8859-8')
    date_col = warn_if_multiple([x for x in latest_df.columns if 'תאריך' in x and 'תאריך ערך' not in x])
    latest_df = latest_df.rename(columns={date_col: 'date', 'סוג פעולה': 'op_type', 'תיאור': 'description', 'אסמכתא': 'id', 'זכות': 'income', 'חובה': 'expense', 'תאריך ערך': 'value_date', 'יתרה': 'balance'})
    latest_df.date = pd.to_datetime(latest_df.date, format='%d/%m/%Y')
    latest_df.value_date = pd.to_datetime(latest_df.value_date, format='%d/%m/%Y')
    for col in ['balance', 'income', 'expense']:
        latest_df[col] = pd.to_numeric(latest_df[col].str.replace(',', ''), errors='coerce')
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
        category_name = '$$ Financial Status $$'
        finance_category = warn_if_multiple([x for x in client.categories() if x['name'] == category_name])
        self.category_id = category_id = finance_category['id']
        user_topics = client.topics_by(dc_username)
        topic_title_to_id = {x['title'].lower(): x['id'] for x in user_topics}
        self.topic_id = topic_title_to_id.get(dc_title.lower())

    def get_last_posted_balance(self):
        # find last post that was posted automatically
        for post in reversed(self.client.posts(self.topic_id)['post_stream']['posts']):
            cooked = post['cooked']
            if ':' not in cooked or 'balance from ' not in cooked:
                continue
            start, end = cooked.rsplit(':', 1)
            balance = float(end.split('<')[0])
            break
        return balance

    def post(self, date, balance):
        content = f'''balance from {date}: {balance}'''
        self.client.create_post(content=content, title=dc_title, category_id=self.category_id, topic_id=self.topic_id)


def df_to_discourse(df):
    status('getting last post')
    client = BalanceDiscourse()
    balance = df.iloc[-1].balance
    last_balance = client.get_last_posted_balance()
    if last_balance == balance:
        status('no change, not posting')
    else:
        status('creating discourse new post')
        date = df.iloc[-1].date.date()
        client.post(date=date, balance=balance)
    status('done')


def main():
    df = export_fibi_actions_from_last_month()
    df_to_discourse(df)


if __name__ == '__main__':
    main()
    #discourse_test()
