# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 23:51:22 2026

@author: thecd
"""

import bs4
from playwright.sync_api import sync_playwright
from playwright.sync_api import expect
import pandas as pd


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
        return page
    expect(page.get_by_text('→', exact=True).first).to_be_visible()
    visible_buttons = []
    for i in range(num_pages):
        if page.get_by_text(f'{i+1}', exact=True).first.is_visible():
            visible_buttons.append(i+1)
            
    if target_page in visible_buttons:
        page.get_by_text(f'{target_page}', exact=True).first.click()
        return page
    
    elif target_page < min(visible_buttons):
        for j in range(min(visible_buttons) - target_page):
            page.get_by_text(f'{min(visible_buttons) - j}', exact=True).first.click()
            expect(page.get_by_text(f'{min(visible_buttons) - j - 1}', exact=True).first).to_be_visible()

        page.get_by_text(f'{target_page}', exact=True).first.click()
        return page
    
    else:
        for j in range(target_page - max(visible_buttons)):
            page.get_by_text(f'{max(visible_buttons) + j}', exact=True).first.click()
            expect(page.get_by_text(f'{max(visible_buttons) + j + 1}', exact=True).first).to_be_visible()
            
        page.get_by_text(f'{target_page}', exact=True).first.click()
        return page
    
    
def get_flight_data(page, ind, num_pages, tag):
    set_page(page, num_pages, ind)

    href = tag.get('href')
    print(href)
    row_tag = page.locator(f'a[href="{href}"]')
    try:
        expect(row_tag).to_be_visible()
    except:
        print(f'Link {href} failed')
        return None
    row_tag.click()            
    expect(page.locator('#extendedDetailsButton')).to_be_visible()
    html2 = page.content()
    soup2 = bs4.BeautifulSoup(html2, 'html.parser')
    
    time_tags = soup2.find_all(time_tag)
    depart_date = soup2.find(depart_date_tag)
    arrival_date = soup2.find(arrive_date_tag)
    
    return page, time_tags, depart_date, arrival_date
    
    
            
    

def get_data(departure, airport, year, month, day, hour):
    link = gen_link(departure, airport, year, month, day, hour)
    
    #launch browser
    playwright = sync_playwright().start()
    browser = playwright.firefox.launch(headless=True)
    page = browser.new_page()
    page.goto(link)

    #clear cookie popup
    try:
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

    

    df = pd.DataFrame(columns=['Time', 'Time Zone', 'Date', 'Increment'])
    failed_links = []

    for i in range(num_pages):
        set_page(page, num_pages, i+1)

        soup1 = bs4.BeautifulSoup(page.content(),'html.parser')
        selected = soup1.find_all(table_tag)
        for tag in selected:
            try:
                page, time_tags, depart_date, arrival_date = get_flight_data(page, i+1, num_pages, tag)
            except:
                print(f'{tag.get("href")} failed')
                failed_links.append(tag.get("href"))
                page.go_back()
                continue
            
            try:
                depart_tag, arrival_tag = time_tags[:2]
                if departure:
                    df = pd.concat([df,pd.DataFrame([{'Time':depart_tag.contents[0], 'Time Zone':depart_tag.contents[1].contents[0], 'Date':depart_date.contents[0], 'Increment':-1}])], ignore_index=True)
                else:
                    df = pd.concat([df,pd.DataFrame([{'Time':arrival_tag.contents[0], 'Time Zone':arrival_tag.contents[1].contents[0], 'Date':arrival_date.contents[0], 'Increment':1}])], ignore_index=True)
            except:
                print(f'{tag.get("href")} failed')
                failed_links.append(tag.get("href"))
            
            page.go_back()
    
    browser.close()
    playwright.stop()
    return df, failed_links
    
df_a, failed_a = get_data(True, 'GLA', 2026, 3, 28, 6)
print(df_a)
print(failed_a)
#df_b , failed_b = get_data(False, 'BHX', 2026, 3, 27, 6)
#print(df_b)
#print(failed_b)
