
# CHF_news_scrapping
Data mining project of gathering data about CHFUSD rate and related news

# solving the problem
to get the neccesary data we use the requests, grequests and BeautifulSoup moduls and their functionality in varius implenetd functions.
The code is built "top down" style

# Functions and Usage
The main function is get_news, that gathers links to news in the website and displays it.
Call get_news with start_date and end_date parameters to desplay all news data from start date to end date.

take_news and get_response are technical functions to scrape the different news links details, and to get request from news links respectively.
output_news prints the data

