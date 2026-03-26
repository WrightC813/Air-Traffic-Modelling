# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 23:51:22 2026

@author: thecd
"""

import bs4
from playwright.sync_api import sync_playwright
from playwright.sync_api import expect
import pandas as pd

link = 'https://www.flightstats.com/v2/flight-tracker/departures/BHX/?year=2026&month=3&date=24&hour=12'

#launch browser
playwright = sync_playwright().start()
browser = playwright.firefox.launch(headless=True)
page = browser.new_page()
page.goto(link)

#clear cookie popup
expect(page.get_by_role("button", name='Accept All Cookies')).to_be_visible()

page.get_by_role('button', name='Accept All Cookies').click()


#toggle to remove codeshares
toggle = page.locator('label[for="toggle-control-undefined"]')
expect(toggle).to_be_visible()
toggle.click()


#find number of pages
num_pages = 1

soup = bs4.BeautifulSoup(page.content(),'html.parser')

def get_nav_buttons(tag):
    if tag.name == "div":
        try:
            classes = tag.get("class")
            return 'pagination__PageNavItem' in str(classes)
        
        except:
            return False

nav_buttons = soup.find_all(get_nav_buttons)
for b in nav_buttons:
    if str(b.text).isdigit():
        num_pages = max(num_pages,int(b.text))


#for each page, click correct navigation button and get flight hyperlinks

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

flight_links = []
df = pd.DataFrame(columns=['Time', 'Time Zone'])

for i in range(num_pages):
    page.get_by_text(f'{i+1}', exact=True).first.click()

    soup = bs4.BeautifulSoup(page.content(),'html.parser')
    selected = soup.find_all(table_tag)
    for tag in selected:
        page.get_by_text(f'{i+1}', exact=True).first.click()
        #page.wait_for_load_state("networkidle")
        href = tag.get('href')
        row_tag = page.locator(f'a[href="{href}"]')
        expect(row_tag).to_be_visible()
        row_tag.click()
        #page.wait_for_load_state("networkidle")
        expect(page.locator('#extendedDetailsButton')).to_be_visible()
        html2 = page.content()
        soup2 = bs4.BeautifulSoup(html2, 'html.parser')
        
        tags = soup2.find_all(time_tag)
        #print(tags)
        try:
            depart_tag, arrival_tag = tags[:2]
            df = pd.concat([df,pd.DataFrame([{'Time':depart_tag.contents[0], 'Time Zone':depart_tag.contents[1].contents[0]}])], ignore_index=True)
            #print(depart_tag.contents[0],depart_tag.contents[1].contents[0])
        except:
            print(f'Link {link} failed')
            continue
        
        page.go_back()
    
    
print(df)


    

browser.close()
playwright.stop()