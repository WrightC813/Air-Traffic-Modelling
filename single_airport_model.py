# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 19:42:11 2026

@author: thecd
"""

from airport_data_scraper import Airport
import pickle
import matplotlib.pyplot as plt

with open('airport_data.pickle', 'rb') as f:
    all_airports = pickle.load(f)
print('Data loaded')
names = []
raw_data = []
for A in all_airports:
    names.append(A.name)
    raw_data.append(A.return_data())

for i, df in enumerate(raw_data):

    plt.step(df['DateTime'],df['Number of Planes'],where='post')
    plt.title(names[i])
    plt.show()
