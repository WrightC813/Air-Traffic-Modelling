Air Traffic Modelling
(Readme file work in progress)

Overview:
This code aims to collect air traffic data, store it in a SQLite database and then train certain models, especially CTMC type models. 

Files:

airport_traffic_scrapper.py is the code which scrapes the website www.flightstats.com for flight data and then saves to a database.

air_traffic_model.py imports the database, processes into Pandas dataframes and the trains the model (still working on last part). Also produces time series plots of each airport.

CTMC_Model.py contains class I am writting to handle the CTMC model. Currently have some of the training written up but need to add features for generating sample paths, measure error against observed data and more.
