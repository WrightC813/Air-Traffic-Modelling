Air Traffic Modelling
(Readme file work in progress)

Overview:
This code aims to collect air traffic data, store it in a SQLite database and then train certain models, especially CTMC type models.

Files:

airport\_traffic\_scrapper.py is the code which scrapes the website www.flightstats.com for flight data and then saves to a database.

air\_traffic\_model.py imports the database, processes into Pandas dataframes and the trains the model. Also produces time series plots of each airport.

CTMC\_Model.py contains class to handle the CTMC model. This class takes care of training the model, generating sample trajectories from the model and estimating the error.



Still to do:

* Cleaning up of code
* Allow model to have fixed parameter structure, i.e. set certain parameters to zero or to be equal
* Implement multiple airport model to take advantage of the information of inter-network flights

