from bs4 import BeautifulSoup
import grequests
import requests

def get_rate(start_datetime, end_datetime, interval):
    """
    gets information about CHFUSD rate within start to end period by inteval
    :param start_datetime: start date or datetime
    :param end_datetime: end date or datetime
    :param interval:
    :return:
    """
    pass

def get_news(start, end):
    """
    returns news from start to end dates
    :param start: start date
    :param end: end date
    :return: list of tuples date - news
    """
    news_page_links = get_news_pages(start, end)
    for link in news_page_links:
        take_news(link)

def main():
    get_rate(start, end, interval)
    get_news(start, end)