Air Traffic Modelling

Overview:
This code aims to collect air traffic data, store it in a SQLite database and then train a custom CTMC (continuous time Markov chain) model on this data

Files Overview:
- airport_data_scraper.py is the file which scrapes the website www.flightstats.com for flight data and then saves to a database.
- CTMC_Model.py contains class to handle the CTMC model, which is time inhomogeneous with a 24h-periodic infinitesimal generator. This class takes care of training the model, generating sample trajectories from the model, estimating the error and solving the differential equations to obtain probability information from the model.
- Exploritory_Analysis.ipynb is a Jupyter notebook containing my analysis of the gathered data, through a number of investigations.
- Mathematical_Model.pdf provides a short mathematical background on the specific Markov chain model.
- airport_data.db contains the SQLite database of all gathered flight data
- airport_data.pickle contains saved python objects defined in airport_data_scraper.py, used to maintain a record of incomplete download data

Dependencies:
- Python with numpy, scipy, bs4,  playwright, pandas, matplotlib
