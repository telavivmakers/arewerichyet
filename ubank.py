#!/usr/bin/env python3

# coding: utf-8

import time
import json
import tempfile
import glob
import os

from selenium import webdriver
import selenium


downloads_dir = tempfile.mkdtemp()

def save_csv(browser):
    while True:
        try:
            e = browser.find_element_by_class_name('excell')
            break
        except selenium.common.exceptions.NoSuchElementException:
            time.sleep(0.5)
            print('.')
    e.click()
    # sleep a bit to let firefox actually save the file - can use inotify? or
    # maybe there is a way to acess the browser's download list directly and
    # avoid races.
    time.sleep(0.5)
    files = glob.glob(os.path.join(downloads_dir, '*.csv'))
    by_mtime = list(sorted([(os.stat(f).st_mtime, f) for f in files]))
    return by_mtime[-1][1]

def get_credentials():
    cred = json.load(open('credentials.json'))
    username = cred['username']
    password = cred['password']
    return username, password

def setup_profile():
    profile = webdriver.FirefoxProfile()
    profile.default_preferences['browser.download.folderList'] = 2
    profile.default_preferences['browser.download.dir'] = downloads_dir
    profile.default_preferences['browser.helperApps.neverAsk.saveToDisk'] = 'application/vnd.ms-excel,text/csv,application/csv,application/x-csv,application/vnd.csv'
    return profile

def login(browser, username, password):
    login_iframe = browser.find_element_by_id('LoginIframeTag')
    browser.switch_to_frame(login_iframe)
    username_element = browser.find_element_by_class_name('fibi_username')
    username_element.clear()
    username_element.send_keys(username)
    password_element = browser.find_element_by_class_name('fibi_password')
    password_element.clear()
    password_element.send_keys(password)
    password_element.send_keys('\n')

# This fails: 1) need to wait for matafTools to be available, so wait for load
# of a certain javascript file, probably just wait for load of the button
# invoking this script 2) fedora/firefox crashes when debugging this script 3)
# setting of profile parameters above does not work, probably wrong mime type,
# also maybe wrong way to setup the preferences.
#browser.execute_script("matafTools.processSaveAs('811','csv','csv');")

def main():
    print("using selenium {}".format(selenium.__version__))
    profile = setup_profile()
    browser = webdriver.Firefox(firefox_profile=profile)
    browser.get('https://online.u-bank.net/wps/portal/FibiMenu/Home')
    print("session id {}".format(browser.session_id))
    username, password = get_credentials()
    login(browser, username, password)

    status_csv = save_csv(browser)
    print("status: {}".format(status_csv))

    # This part is slow due to many accesses via selenium? can fix the XPATH to
    # make it faster. Full text is TNUOT BAHESHBON - תנועות בחשבון
    spans=browser.find_elements_by_xpath('//span')
    operations_span = [s for s in spans if 'בחשבון' in s.text][0]
    operations_span.click()

    operations_csv = save_csv(browser)
    print("operations: {}".format(status_csv))

if __name__ == '__main__':
    main()
