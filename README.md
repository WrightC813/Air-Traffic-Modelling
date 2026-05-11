Air Traffic Modelling
(Readme file work in progress)

Overview:
This code aims to collect air traffic data, store it in a SQLite database and then train certain models, especially CTMC type models. 

Files:

airport_traffic_scrapper.py is the code which scrapes the website www.flightstats.com for flight data and then saves to a database.

air_traffic_model.py imports the database, processes into Pandas dataframes and the trains the model (still working on last part). Also produces time series plots of each airport.

CTMC_Model.py contains class to handle the CTMC model. This class takes care of training the model, generating sample trajectories from the model and estimating the error
