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
import pickle
import sqlite3
    

class Airport:
    def __init__(self, code, name):
        #code is airport code used by website
        self.code = code
        #name is display name
        self.name = name
        #df stores all arrival and departure information
        self.data_df = pd.DataFrame(columns=['Flight Code', 'DateTime', 'Time Zone', 'Increment', 'Other Airport Code'])
        #df storing time segments of data, with download status
        self.segments_df = pd.DataFrame(columns=['Date', 'Departure', 'Time Slot', 'Downloaded'])
        self.mean_delay = 0.5
        self.date_dict = {'Jan':1, 'Feb':2, 'Mar':3, 'Apr':4, 'May':5, 'Jun':6,
                     'Jul':7, 'Aug':8, 'Sep':9, 'Oct':10, 'Nov':11, 'Dec':12}
        #df to store partial downloads
        self.partial_df = pd.DataFrame(columns=['Flight Code', 'DateTime', 'Time Zone', 'Increment', 'Other Airport Code', 'Href'])
        self.partial_params = {}
        
        
    def fill_segments_df(self):
        #function to compute dates, times and arrivals/departures to add the the download queue
        today = datetime.date.today()
        day = datetime.timedelta(days=1)
        dates = [today - day, today - 2*day, today - 3*day]
        df_t = pd.DataFrame()
        for d in dates:
            for dept in (True, False):
                for i in range(4):
                    df_t = pd.concat([df_t, pd.DataFrame([{'Date':d, 'Departure':dept, 'Time Slot':i, 'Downloaded':False}])],ignore_index=True)
        self.segments_df = pd.concat([self.segments_df,df_t], ignore_index=True).drop_duplicates(subset=['Date', 'Departure', 'Time Slot'])
        self.segments_df = self.segments_df.sort_values(['Date', 'Departure', 'Time Slot'])
        
    def get_data_segment(self):
        #Primary function to obtain a segment of flight data
        #If all recent data is already downloaded, return None
        if self.segments_df.tail(24)['Downloaded'].all():
            return None
        
        #If the previous download was interupted, continue it
        if len(self.partial_df)> 0:
            print('Partial Params', self.partial_params)
            ind = self.segments_df.loc[(self.segments_df['Departure'] == self.partial_params['Departure']) & ((self.segments_df['Date'] == self.partial_params['Date']) & (self.segments_df['Time Slot'] == self.partial_params['Time Slot']))].index[0]
            if ind < len(self.segments_df) - 24:
                print('Partial Params now out of range')
                self.partial_df = pd.DataFrame(columns=['Flight Code', 'DateTime', 'Time Zone', 'Increment', 'Href'])
                self.partial_params = {}
                ind = list(self.segments_df['Downloaded'].values)[-24:].index(False) + max(len(self.segments_df) - 24,0)
            
        else:
            ind = list(self.segments_df['Downloaded'].values)[-24:].index(False) + max(len(self.segments_df) - 24,0)

        departure = self.segments_df['Departure'].iloc[ind]
        year = self.segments_df['Date'].iloc[ind].year
        month = self.segments_df['Date'].iloc[ind].month
        day = self.segments_df['Date'].iloc[ind].day
        hour = self.segments_df['Time Slot'].iloc[ind] * 6
        
        if departure:
            print(f'{self.name}: Departures on {day}-{month}-{year} between {hour}h and {hour + 6}h')
        if not departure:
            print(f'{self.name}: Arrivals on {day}-{month}-{year} between {hour}h and {hour + 6}h')
        
        try:
            df_t, blocked = self.get_data(departure, self.code, year, month, day, hour)
        except:
            print('Failed to download these flights')
            return None
        if blocked:
            print('Download not completed, suspect website blocked us')
            return None

        #If sucessful and not blocked, store data and mark this segment as downloaded
        self.data_df = (pd.concat([self.data_df,df_t], ignore_index=True).sort_values('DateTime')).drop_duplicates(subset=['Flight Code', 'DateTime'])
        self.segments_df.loc[self.segments_df.index[ind],'Downloaded'] = True
        
        
    def gen_link(self, departure, airport, year, month, day, hour):
        #Generate the website address
        link = 'https://www.flightstats.com/v2/flight-tracker/'
        if departure:
            link = link + 'departures/'
        else:
            link = link + 'arrivals/'
        link = link + f'{airport}/?year={year}&month={month}&date={day}&hour={hour}'
        return link
    
    def get_nav_buttons(self,tag):
        #Function to find html tags for navigation buttons
        if tag.name == "div":
            try:
                classes = tag.get("class")
                return 'pagination__PageNavItem' in str(classes)
            
            except:
                return False
                    
    def table_tag(self,tag):
        #Function to find html tags of rows of the table of flights
        if tag.name == "a":
            try:
                classes = tag.get("class")
                has_hyp = tag.get("href") != None
                return 'table__A' in str(classes) and has_hyp
            
            except:
                return False
            
    def time_tag(self,tag):
        #Function to find the times from the page for a specific flight
        pr = tag.find_previous_sibling('div')
        try:
            if pr.string == 'Actual':
                return True
        except:
            return False
           
    def depart_date_tag(self,tag):
        #Function to find the date of departure for a specific flight
        pr = tag.find_previous_sibling('div')
        try:
            if pr.string == 'Flight Departure Times':
                return True
        except:
            return False
          
    def arrive_date_tag(self,tag):
        #Function to find the date of arrival for a specific flight
        pr = tag.find_previous_sibling('div')
        try:
            if pr.string == 'Flight Arrival Times':
                return True
        except:
            return False
             
    def set_page(self, page, num_pages, target_page):
        #Function to navigate to a specific page of flights for a given data segment
        #If only one page, nothing to do
        if num_pages == 1:
            return page, False
        #Wait for the page to load by looking for expected item
        try:
            expect(page.get_by_text('→', exact=True).first).to_be_visible()
        except:
            return page, True
        visible_buttons = []
        #Find currently visible page number buttons
        for i in range(num_pages):
            if page.get_by_text(f'{i+1}', exact=True).first.is_visible():
                visible_buttons.append(i+1)
                
        #If already visible, press desired page button
        if target_page in visible_buttons:
            page.get_by_text(f'{target_page}', exact=True).first.click()
            return page, False
        
        #Otherwise click through until we reach desired page
        elif target_page < min(visible_buttons):
            for j in range(min(visible_buttons) - target_page):
                time.sleep(0.1 + random.expovariate(self.mean_delay))
                page.get_by_text(f'{min(visible_buttons) - j}', exact=True).first.click()
                expect(page.get_by_text(f'{min(visible_buttons) - j - 1}', exact=True).first).to_be_visible()

            page.get_by_text(f'{target_page}', exact=True).first.click()
            return page, False
        
        else:
            for j in range(target_page - max(visible_buttons)):
                time.sleep(0.1 + random.expovariate(self.mean_delay))
                page.get_by_text(f'{max(visible_buttons) + j}', exact=True).first.click()
                expect(page.get_by_text(f'{max(visible_buttons) + j + 1}', exact=True).first).to_be_visible()
                
            page.get_by_text(f'{target_page}', exact=True).first.click()
            return page, False
         
    def get_flight_data(self, page, ind, num_pages, tag, departure):
        #Function to extract data from one given flight
        page, blocked = self.set_page(page, num_pages, ind)
        if blocked:
            return page, pd.DataFrame(), True

        #Obtain the flight code from the website address
        href = tag.get('href')
        flight_code = ' '.join(href.split('?')[0].split('/')[-2:])
        
        time.sleep(0.1 + random.expovariate(self.mean_delay))
        try:
            #Gets scheduled times in case flight date now out of range
            l = tag.get_text().split(':')
            expected_depart = [l[0][-2:], l[1][:2]]
            expected_arrival = [l[1][-2:], l[2][:2]]
            other_airport = l[2][2:5]
            page.locator(f'a[href="{href}"]').click()
        except:
            print(f'{flight_code} failed, could not click flight row')
            return page, pd.DataFrame(), True  
        #Load, if possible, the page for the specified flight
        try:
            expect(page.locator('a[href="/v2/historical-flight/search"]').first).to_be_visible()
        except:
            print(f'{flight_code} failed, page did not load')
            return page, pd.DataFrame(), True 
            
        #Extract the html of the page
        html2 = page.content()
        soup2 = bs4.BeautifulSoup(html2, 'html.parser')
        
        #If date is now out of range, use the scheduled data if possible
        if 'DATE IS OUT OF RANGE' in soup2.get_text():
            print(f'{flight_code} failed, date now out of range. Trying Expected Values')
            try:
                if departure:
                    t = expected_depart
                    inc = -1
                else:
                    t = expected_arrival
                    inc = 1
                url = page.url.split('&')
                date = url[-2].split('=')[-1]
                month = url[-3].split('=')[-1]
                year = url[-4].split('=')[-1]
                dts = datetime.datetime(int(year), int(month), int(date), int(t[0]), int(t[1]))
                df = pd.DataFrame([{'Flight Code':flight_code,'DateTime':dts.strftime("%Y-%m-%d %H:%M"), 'Time Zone':None,  'Increment':inc, 'Other Airport Code':other_airport, 'Href':href}])
                #print(df)
                return page, df, False
            except:
                print('Could not use expected values')
                return page, pd.DataFrame(), False
            
        #Dealing with certain known exceptional cases
        if 'Flight Status Not Available' in soup2.get_text():
            print(f'{flight_code} failed, flight status not available')
            return page, pd.DataFrame(), False
        
        if 'Flight Cancelled' in soup2.get_text():
            print(f'{flight_code} failed, flight cancelled')
            return page, pd.DataFrame(), False
        
        #Aims to catch when the website has blocked us, as we always expect the flight code on the page
        if flight_code not in soup2.get_text().strip('()'):
            print(f'{flight_code} failed, code not found on page')
            return page, pd.DataFrame(), True
        
        #Obtain the flight data
        time_tags = soup2.find_all(self.time_tag)
        depart_date = soup2.find(self.depart_date_tag)
        arrival_date = soup2.find(self.arrive_date_tag)
        
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
            dts = datetime.datetime(int(d[2]), self.date_dict[d[1]], int(d[0]), int(t[0]), int(t[1]))
            df = pd.DataFrame([{'Flight Code':flight_code,'DateTime':dts.strftime("%Y-%m-%d %H:%M"), 'Time Zone':tz,  'Increment':inc, 'Other Airport Code':other_airport, 'Href':href}])
            return page, df, False
        except:
            print(f'{flight_code} failed, tags contain no time data')
            return page, pd.DataFrame(), False
        
        
    def get_data(self, departure, airport, year, month, day, hour):
        #Function to manage the web session for one segment of data
        link = self.gen_link(departure, airport, year, month, day, hour)
        blocked = False
        
        #launch browser
        playwright = sync_playwright().start()
        browser = playwright.firefox.launch(headless=True)
        page = browser.new_page()
        page.goto(link)

        #clear cookie popup
        try:
            expect(page.get_by_role("button", name='Cookies Settings')).to_be_visible()
            time.sleep(0.1 + random.expovariate(self.mean_delay))
            page.get_by_role('button', name='Cookies Settings').click()
            expect(page.get_by_role("button", name='Confirm My Choices')).to_be_visible()
            time.sleep(0.1 + random.expovariate(self.mean_delay))
            page.get_by_role('button', name='Confirm My Choices').click()
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
        nav_buttons = soup.find_all(self.get_nav_buttons)
        for b in nav_buttons:
            if str(b.text).isdigit():
                num_pages = max(num_pages,int(b.text))

        
        df = pd.DataFrame(columns=['Flight Code', 'DateTime', 'Time Zone', 'Increment', 'Other Airport Code', 'Href'])
        
        #Loop through all the pages of flights
        for i in range(num_pages):
            print(f'Page {i+1} of {num_pages}:')
            self.set_page(page, num_pages, i+1)

            soup1 = bs4.BeautifulSoup(page.content(),'html.parser')
            selected = soup1.find_all(self.table_tag)
            #Loop through flights on this page
            for tag in selected:
                href = tag.get('href')
                flight_code = ' '.join(href.split('?')[0].split('/')[-2:])
                print(flight_code)
                if href in self.partial_df['Href'].values:
                    print('Already downloaded')
                    continue
                try:
                    page, df_t, blocked_t = self.get_flight_data(page, i+1, num_pages, tag, departure)
                except:
                    print('Failed to get data')
                    time.sleep(0.1 + random.expovariate(self.mean_delay))
                    page.go_back()
                    continue
                
                if blocked_t:
                    print('Suspect website blocked us')
                    blocked = True
                    break
                
                try:
                    df = pd.concat([df,df_t], ignore_index=True)
                except:
                    print(f'{tag.get("href")} failed to add data')
                time.sleep(0.1 + random.expovariate(self.mean_delay))
                page.go_back()
            if blocked:
                break
        browser.close()
        playwright.stop()
        
        if blocked:
            self.partial_df = pd.concat([self.partial_df,df], ignore_index=True)
            self.partial_params['Date'] = datetime.date(year, month, day)
            self.partial_params['Departure'] = departure
            self.partial_params['Time Slot'] = int(hour/6)
            return df[['Flight Code', 'DateTime', 'Time Zone', 'Increment', 'Other Airport Code']], blocked

        
        if not blocked:
            df = pd.concat([self.partial_df,df], ignore_index=True)
            self.partial_df = pd.DataFrame(columns=['Flight Code', 'DateTime', 'Time Zone', 'Increment', 'Href'])
            self.partial_params = {}
            return df[['Flight Code', 'DateTime', 'Time Zone', 'Increment', 'Other Airport Code']], blocked
    
    
    
    def reset_df(self):
        self.data_df = pd.DataFrame(columns=['Flight Code', 'DateTime', 'Time Zone', 'Increment', 'Other Airport Code'])
    

            
if __name__ == '__main__':
    #Load python objects containing airport information and all partial downloads
    with open('airport_data.pickle', 'rb') as f:
        all_airports = pickle.load(f)
    print('Data loaded')
    #Shuffle to randomise the order of downloads 
    random.shuffle(all_airports)

    #Initialise database connection
    conn = sqlite3.connect('airport_data.db', isolation_level=None)
    #Add airports table if it doesn't already exist
    conn.execute('CREATE TABLE IF NOT EXISTS airports (name TEXT NOT NULL, code TEXT NOT NULL) STRICT')
    
    #Add flight data table if it doesn't already exist
    conn.execute('CREATE TABLE IF NOT EXISTS flights (airport TEXT NOT NULL, flight_code TEXT, flight_datetime TEXT, timezone TEXT, increment INT, other_airport TEXT) STRICT')
    for A in all_airports:
        name = A.name.lower().replace(' ','_')
        #Add airport to airports table if not already there
        if conn.execute('SELECT * FROM airports WHERE name=?', [A.name]).rowcount == 0:
            conn.execute('INSERT INTO airports VALUES (?,?)', [A.name,A.code])
        
        #Fetching data for airport A
        A.reset_df()
        A.fill_segments_df()
        A.get_data_segment()
        #If data gathering interupted, don't add to database.
        if len(A.partial_df) > 0:
            print('Data collection incomplete')
            print(A.partial_df)
        #If data gathering complete, add new entries to database
        else:
            print('Saving to database')
            for f in A.data_df.itertuples():
                conn.execute('INSERT INTO flights VALUES (?,?,?,?,?,?)', [A.code, f[1], f[2], f[3], f[4], f[5]])
        
        #Displaying how much more availbale data for airport A
        n = len(A.segments_df.tail(24).loc[A.segments_df["Downloaded"] == False])
        if n > 0:
            print(f'{n} time segments still to download')
            time.sleep(random.expovariate(5))
        else:
            print(f'{A.name} has all available data downloaded')

    #Saving both python airport objects and closing database connection
    with open('airport_data.pickle', 'wb') as f:
        pickle.dump(all_airports, f, pickle.HIGHEST_PROTOCOL)
    conn.close()
    print('Data objects saved')

