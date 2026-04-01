# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 23:51:22 2026

@author: thecd
"""

import bs4
from playwright.sync_api import sync_playwright
from playwright.sync_api import expect
import pandas as pd
import random
import time
import datetime

mean_delay = 1
long_delay = 9
date_dict = {'Jan':1, 'Feb':2, 'Mar':3, 'Apr':4, 'May':5, 'Jun':6,
             'Jul':7, 'Aug':8, 'Sep':9, 'Oct':10, 'Nov':11, 'Dec':12}


# %% Main function which takes in high level info and refurns data frame with from this page

def gen_link(departure, airport, year, month, day, hour):
    link = 'https://www.flightstats.com/v2/flight-tracker/'
    if departure:
        link = link + 'departures/'
    else:
        link = link + 'arrivals/'
    link = link + f'{airport}/?year={year}&month={month}&date={day}&hour={hour}'
    return link

def get_nav_buttons(tag):
    if tag.name == "div":
        try:
            classes = tag.get("class")
            return 'pagination__PageNavItem' in str(classes)
        
        except:
            return False
        
        
def table_tag(tag):
    if tag.name == "a":
        try:
            classes = tag.get("class")
            has_hyp = tag.get("href") != None
            return 'table__A' in str(classes) and has_hyp
        
        except:
            return False
        
        
def time_tag(tag):
    pr = tag.find_previous_sibling('div')
    try:
        if pr.string == 'Actual':
            return True
    except:
        return False
    
def depart_date_tag(tag):
    pr = tag.find_previous_sibling('div')
    try:
        if pr.string == 'Flight Departure Times':
            return True
    except:
        return False
    
def arrive_date_tag(tag):
    pr = tag.find_previous_sibling('div')
    try:
        if pr.string == 'Flight Arrival Times':
            return True
    except:
        return False
    
def set_page(page, num_pages, target_page):
    if num_pages == 1:
        return page, False
    try:
        expect(page.get_by_text('→', exact=True).first).to_be_visible()
    except:
        return page, True
    visible_buttons = []
    for i in range(num_pages):
        if page.get_by_text(f'{i+1}', exact=True).first.is_visible():
            visible_buttons.append(i+1)
            
    if target_page in visible_buttons:
        page.get_by_text(f'{target_page}', exact=True).first.click()
        return page, False
    
    elif target_page < min(visible_buttons):
        for j in range(min(visible_buttons) - target_page):
            time.sleep(random.expovariate(mean_delay))
            page.get_by_text(f'{min(visible_buttons) - j}', exact=True).first.click()
            expect(page.get_by_text(f'{min(visible_buttons) - j - 1}', exact=True).first).to_be_visible()

        page.get_by_text(f'{target_page}', exact=True).first.click()
        return page, False
    
    else:
        for j in range(target_page - max(visible_buttons)):
            time.sleep(random.expovariate(mean_delay))
            page.get_by_text(f'{max(visible_buttons) + j}', exact=True).first.click()
            expect(page.get_by_text(f'{max(visible_buttons) + j + 1}', exact=True).first).to_be_visible()
            
        page.get_by_text(f'{target_page}', exact=True).first.click()
        return page, False
    
    
def get_flight_data(page, ind, num_pages, tag, departure):
    page, blocked = set_page(page, num_pages, ind)
    if blocked:
        return page, pd.DataFrame(), True

    href = tag.get('href')
    flight_code = ' '.join(href.split('?')[0].split('/')[-2:])
    
    time.sleep(random.expovariate(mean_delay))
    try:
        page.locator(f'a[href="{href}"]').click()
    except:
        print(f'{flight_code} failed, could not click flight row')
        return page, pd.DataFrame(), True  
    expect(page.locator('#extendedDetailsButton')).to_be_visible()
    html2 = page.content()
    soup2 = bs4.BeautifulSoup(html2, 'html.parser')
        
    if flight_code not in soup2.get_text():
        print(f'{flight_code} failed, code not found on page')
        return page, pd.DataFrame(), True
    
    if 'Flight Cancelled' in soup2.get_text():
        print(f'{flight_code} failed, flight cancelled')
        return page, pd.DataFrame(), False
    
    time_tags = soup2.find_all(time_tag)
    depart_date = soup2.find(depart_date_tag)
    arrival_date = soup2.find(arrive_date_tag)
    
    try:
        depart_tag, arrival_tag = time_tags[:2]
        if departure:
            ti = depart_tag.contents[0]
            da = depart_date.contents[0]
            tz = depart_tag.contents[1].contents[0]
            inc = -1
        else:
            ti = arrival_tag.contents[0]
            da = arrival_date.contents[0]
            tz = arrival_tag.contents[1].contents[0]
            inc = 1
        t = ti.split(':')
        d = da.split('-')
        dts = datetime.datetime(int(d[2]), date_dict[d[1]], int(d[0]), int(t[0]), int(t[1]))
        df = pd.DataFrame([{'Flight Code':flight_code,'DateTime':dts, 'Time Zone':tz,  'Increment':inc}])
        print(flight_code)
        return page, df, False
    except:
        print(f'{flight_code} failed, tags contain no time data')
        return page, pd.DataFrame(), False
        
    

def get_data(departure, airport, year, month, day, hour):
    link = gen_link(departure, airport, year, month, day, hour)
    blocked_overall = False
    
    #launch browser
    playwright = sync_playwright().start()
    browser = playwright.firefox.launch(headless=True)
    page = browser.new_page()
    page.goto(link)

    #clear cookie popup
    try:
        time.sleep(random.expovariate(mean_delay))
        expect(page.get_by_role("button", name='Accept All Cookies')).to_be_visible()
        page.get_by_role('button', name='Accept All Cookies').click()
    except:
        pass


    #toggle to remove codeshares
    try:
        toggle = page.locator('label[for="toggle-control-undefined"]')
        expect(toggle).to_be_visible()
        toggle.click()
    except:
        return None


    #find number of pages
    num_pages = 1
    soup = bs4.BeautifulSoup(page.content(),'html.parser')
    nav_buttons = soup.find_all(get_nav_buttons)
    for b in nav_buttons:
        if str(b.text).isdigit():
            num_pages = max(num_pages,int(b.text))

    
    df = pd.DataFrame(columns=['Flight Code', 'DateTime', 'Time Zone', 'Increment'])
    failed_links = []

    for i in range(num_pages):
        print(f'Page {i+1} of {num_pages}:')
        set_page(page, num_pages, i+1)

        soup1 = bs4.BeautifulSoup(page.content(),'html.parser')
        selected = soup1.find_all(table_tag)
        for tag in selected:
            try:
                page, df_t, blocked = get_flight_data(page, i+1, num_pages, tag, departure)
            except:
                print('Failed to get data')
                failed_links.append(tag.get("href"))
                time.sleep(random.expovariate(mean_delay))
                page.go_back()
                continue
            
            if blocked:
                print('Suspect website blocked us')
                blocked_overall = True
                break
            
            try:
                df = pd.concat([df,df_t], ignore_index=True)
            except:
                print(f'{tag.get("href")} failed to add data')
                failed_links.append(tag.get("href"))
            time.sleep(random.expovariate(mean_delay))
            page.go_back()
        if blocked_overall:
            break
    
    browser.close()
    playwright.stop()
    return df, failed_links, blocked_overall
    

df = pd.DataFrame()
failed = []
airport = 'KOI'

to_retry = []

for dept in (True, False):
    for i in range(4):
        if dept:
            print(f'Departures from {6*i}h to {6*(i+1)}h')
        if not dept:
            print(f'Arrivals from {6*i}h to {6*(i+1)}h')
        try:
            df_t, failed_t, blocked = get_data(dept, airport, 2026, 3, 31, 6*i)
            if blocked:
                to_retry.append((dept,i))
                time.sleep(long_delay + random.expovariate(mean_delay))
                continue
            failed = failed + failed_t
            df = pd.concat([df,df_t], ignore_index=True)
        except:
            print('No data extracted')

if len(to_retry) > 0:
    print('Retrying blocked pages')
    time.sleep(long_delay + random.expovariate(mean_delay))
    for p in to_retry:
        dept, i = p
        if dept:
            print(f'Departures from {6*i}h to {6*(i+1)}h')
        if not dept:
            print(f'Arrivals from {6*i}h to {6*(i+1)}h')
        try:
            df_t, failed_t, blocked = get_data(dept, airport, 2026, 3, 30, 6*i)
            if blocked:
                print('Blocked again')
            failed = failed + failed_t
            df = pd.concat([df,df_t], ignore_index=True)
        except:
            print('No data extracted')

print(df.sort_values('DateTime'))
print(failed)