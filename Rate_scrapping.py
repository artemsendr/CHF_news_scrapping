import argparse
import re
from bs4 import BeautifulSoup
import grequests
import requests
from datetime import datetime
import pandas as pd


HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '3600',
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'
}
SITE_URL = 'https://www.investing.com'
NEWS_URL = 'https://www.investing.com/currencies/usd-chf-news/'
TECHNICAL_URL = 'https://www.investing.com/currencies/usd-chf-technical/'
FORUM_URL = 'https://www.investing.com/currencies/usd-chf-commentary/'


def get_rate(start_datetime, end_datetime, interval):
    """
    gets information about CHFUSD rate within start to end period by inteval
    :param start_datetime: start date or datetime
    :param end_datetime: end date or datetime
    :param interval:
    :return:
    """
    pass


def get_forum_page(url):
    response = get_response(url, HEADERS)

    soup = BeautifulSoup(response.content, 'html.parser')
    df = pd.DataFrame(columns=['id', 'instrument_id', 'parent_id','username', 'postdate', 'comment_text'], index=['id'])
    comment_tree = soup.findAll(class_='discussion-list_comments__3rBOm pb-2 border-0')
    for comments in comment_tree:
        comment = comments.find(class_='comment_comment-wrapper__hJ8sd')
        print(comment)
        """user = comment.find(class_="comment_user-info__AWjKG")
        username = user.findChildren("a", recursive=False)[0]
        username = username.text
        postdate = user.findChildren("span", recursive=False)[0]
        postdate = postdate.text
        print(username, postdate)"""


def set_technical_period():
    """
    makes TECHNICAL_URL page show Monthly recommendations.
    :return:
    """
    pass


def get_technical(url):
    """
    srape TECHNICAL_URL page and returns pandas data frame with all techincals
    :param url: url address of page with techicals
    :return: ['Name', 'Value', 'Action'] technicals
    """
    set_technical_period()
    response = get_response(url, HEADERS)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', class_='genTbl closedTbl technicalIndicatorsTbl smallTbl float_lang_base_1')
    # Defining of the dataframe
    df = pd.DataFrame(columns=['Name', 'Value', 'Action'])

    for row in table.tbody.find_all('tr'):
        # Find all data for each column
        columns = row.find_all('td')

        if len(columns) == 3:
            name = columns[0].text.strip()
            value = columns[1].text.strip()
            action = columns[2].text.strip()
            dc = {'Name': name, 'Value': value, 'Action': action}
            #df = df.append({'Name': name, 'Value': value, 'Action': action}, ignore_index=True)
            df = pd.concat([pd.DataFrame(dc, index=[0]), df.loc[:]]).reset_index(drop=True)
    return df

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


def get_news_pages(start, end):
    """
    :param start: start date of news scrapping
    :param end: end date of news scrapping
    :return: list of links to news pages from start to end date
    """
    summary_url = NEWS_URL
    break_condition = True
    news_links = []
    page_number = 1
    while break_condition:
        response = get_response(summary_url, HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        news_items = soup.findAll(class_="articleDetails")
        for news in news_items:
            date_scope = news.find(class_="date").text
            date = date_scope.replace(u'\xa0', "")
            date = date.strip("- ")
            date_news = datetime.strptime(date, '%b %d, %Y')
            if start <= date_news <= end:
                url = news.parent.find("a").get('href')
                news_links.append(SITE_URL + url)
            elif date_news < start:
                break_condition = False
                break
        # go to next page
        page_number += 1
        summary_url = NEWS_URL + str(page_number)
    return news_links

def take_news(links):
    """
    take single news text by link
    :param links: list url to news
    :return: news
    """
    link = links
    #news = []
    #for link in links:
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
    news_text = news_text[:-1]

    if re.search('^By ', author):
        author = author[3:]

    date = soup.find(class_="contentSectionDetails").select_one('span').text
    return {'date': date, 'author': author, 'text': news_text}


def get_response(url, header):
    """
    return response object on get
    :param url: any url link
    :param header: header of request
    :return: response object on get request
    """
    try:
        response = requests.get(url, header)
        return response
    except Exception:
        raise ConnectionError("Connection error during request directors of %s" % url)

def output_news(news):
    """
    print, print to file,.. news
    :param news: dict of items connected to news (date, text,...)
    :return: nothing
    """
    print(f"date: {news['date']}\n\n text: \n {news['text']}")

def main():
    #get_rate(start, end, interval)
    #get_news(datetime(2020, 2, 25), datetime(2022, 7, 11))
    #test_url = ['https://www.investing.com/news/forex-news/dollar-soars-against-the-yen-after-boj-stands-pat-2838157']
    #take_news(test_url)
    #print(get_news_pages(datetime(2020, 2, 25), datetime(2022, 7, 11)))
    #print(get_technical(TECHNICAL_URL))
    get_forum_page(FORUM_URL)


def command_parser():
    parser = argparse.ArgumentParser(description='parsing data options')
    FUNCTION_MAP = {'news': get_news,
                    'technical':get_technical}

    parser.add_argument('command', choices=FUNCTION_MAP.keys())
    parser.add_argument('-n', '--news', help="news command", required=False)
    parser.add_argument('-t', '--technical', help="technical command", required=False)
    args = parser.parse_args()
    return parser
    # func = FUNCTION_MAP[args.command]
    # func()
    # parser.parse_args()
    # input_args = parser.parse_args()
    # data_functions = {'get_news': get_news, 'get_technical': get_technical}
    # data_functions[input_args.action](input_args.first_arg,input_args.second_arg)
    return parser


#     parser = argparse.ArgumentParser(description='parsing data options')
#     parser.add_argument('get_technical', help='gets the technicals from website')
#     parser.add_argument('url', type=str, help='gets the technicals from website')
#     parser.add_argument('get_news')
#     parser.add_argument('start', type=datetime)
#     parser.add_argument('end', type=datetime)
#     parser.parse_args()

main()
