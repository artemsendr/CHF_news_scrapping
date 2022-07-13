import re

from bs4 import BeautifulSoup
import grequests
import requests

HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '3600',
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'
}


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
        news = take_news(link)
        output_news(news)



def take_news(links):
    """
    take single news text by link
    :param links: list url to news
    :return: news
    """
    link = links[0]
    response = get_response(link, HEADERS)
    soup = BeautifulSoup(response.content, 'html.parser')
    news_section = soup.find(class_="WYSIWYG articlePage")
    author =''
    news_text =''
    for parts in news_section.findChildren("p"):
        if author == '':
            author = parts.text
        else:
            news_text += parts.text + '\n'
    news_text = news_text [:-1]

    if re.search('^By ', author):
        author = author[3:]

    date = soup.find(class_="contentSectionDetails").select_one('span').text

    print(news_text)
    print(date)
    print(author)
    return (date,author, news_section)

def get_response(film_url, header):
    try:
        response = requests.get(film_url, header)
        return response
    except Exception:
        raise ConnectionError("Connection error during request directors of %s" % film_url)

def output_news(news):
    """
    print, print to file,.. news
    :param news: tuple of items connected to news (date, text,...)
    :return: nothing
    """
    pass

def main():
    #get_rate(start, end, interval)
    #get_news(start, end)
    test_url = ['https://www.investing.com/news/forex-news/dollar-soars-against-the-yen-after-boj-stands-pat-2838157']
    take_news(test_url)


main()