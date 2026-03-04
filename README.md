[![DOI](https://zenodo.org/badge/657341621.svg)](https://zenodo.org/doi/10.5281/zenodo.10383685)

# ICD-11 Data Retriever package 

Package designed to make working with hierarchy of ICD-11 data more manageable for NLP and other data science projects.


# ICD11-Retriever



Reference ICD-11 API is here:  https://icd.who.int/browse/2026-01/mms/en
API Documentation for ICD-11 is here:  https://icd.who.int/icdapi

## Features

- API process extracts all data from a starting ICD11 node (Default is "Mental, behavioural or neurodevelopmental disorders", entity# 334423054)
- Uses graph traversal to retrieve parent/child relationships of ICD11 data
- Quickly retrieve organized groupings of ICD11 data
- 

## Installation


## Quick start

To run a new API extract, ICD_CLIENT_SECRET and ICD_CLIENT_ID are required (see ICD-11 API documentation)

input arguments options (to traverse alternate ICD-11 starting nodes):
--startnode, type = str, default = "Mental, behavioural or neurodevelopmental disorders"
--startid, type = str, default = "334423054"


## Links or References


