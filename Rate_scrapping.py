import re
import logging
import argparse

import numpy as np
from bs4 import BeautifulSoup
# import grequests
import requests
from datetime import datetime, timedelta
import pandas as pd
# pip install webdriver-manager
# service = Service(executable_path=ChromeDriverManager().install())
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By


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
    url = 'https://api.exchangerate.host/timeseries?start_date=2020-01-01&end_date=2020-01-04'
    response = requests.get(url)
    data = response.json()

    print(data)


def get_forum(url, start_date, end_date):
    """
    get forum messages by url of first comments page and parse it to nice structure
    :param url: url of comments page (first one), str
    :param start_date: start date of scraping(the most recent to be scraped)
    :param end_date: end date of scraping (the latest date of scraping)
    :return: pandas data frame columns = ['id', 'instrument_id', 'parent_id', 'username', 'postdate', 'comment_text'],
                      index=['id']
    """
    logging.info("forum scraping started, url = %s", url)
    service = Service(executable_path=ChromeDriverManager().install())
    logging.debug("Service installed")
    driver = webdriver.Chrome(service=service)
    logging.debug("Driver launched")
    break_condition = False
    page_number = 1
    id_ = 1
    purl = url
    df = pd.DataFrame(columns=['id', 'instrument_id', 'parent_id', 'username', 'postdate', 'comment_text'],
                      index=['id'])
    while not break_condition:
        driver.get(purl)
        logging.info("Page %s loaded", purl)
        driver.implicitly_wait(5)
        response = driver.page_source

        soup = BeautifulSoup(response, 'html.parser')
        comment_tree = soup.find(class_='discussion-list_comments__3rBOm pb-2 border-0')
        comment_tree = list(comment_tree.children)[0].findChildren(class_='list_list__item__1kZYS', recursive=False)
        break_condition = False
        for comment in comment_tree:
            #comment = comments.find(class_='comment_comment-wrapper__hJ8sd')
            user = comment.find(class_="comment_user-info__AWjKG")
            username = user.findChildren("a", recursive=False)[0]
            username = username.text
            postdate = user.findChildren("span", recursive=False)[0]
            try:
                postdate = date_converter(postdate.text)
            except ValueError:
                logging.error("Error while converting %s to date format on page %s", postdate.text, url)
                postdate = pd.NaN
            if postdate > end_date:
                continue
            if postdate < start_date:
                break_condition = True
                break
            comment_text = comment.find(class_="comment_content__AvzPV").text
            subcomment_tree = comment.find(class_="list_list--underline__dWxSt discussion_replies-wrapper__3sWFn").children
            dc = {'id': id_, 'instrument_id':'', 'parent_id': pd.NaN, 'username': username, 'postdate': postdate,
                  'comment_text': comment_text}
            parent_id = id_
            id_ += 1
            df = pd.concat([pd.DataFrame(dc, index=[0]), df.loc[:]]).reset_index(drop=True)
            for subcomment in subcomment_tree:
                user = subcomment.find(class_="comment_user-info__AWjKG")
                username = user.findChildren("a", recursive=False)[0]
                username = username.text
                postdate = user.findChildren("span", recursive=False)[0]
                try:
                    postdate = date_converter(postdate.text)
                except ValueError:
                    logging.error("Error while converting %s to date format on page %s", postdate.text, url)
                    postdate = pd.NaN
                comment_text = subcomment.find(class_="comment_content__AvzPV").text
                dc = {'id': id_, 'instrument_id': '', 'parent_id': parent_id, 'username': username, 'postdate': postdate,
                      'comment_text': comment_text}
                id_ += 1
                df = pd.concat([pd.DataFrame(dc, index=[0]), df.loc[:]]).reset_index(drop=True)
        page_number += 1
        purl = url + "/" + str(page_number)
    logging.info("forum scraping started, url = %s", url)
    return df


def date_converter(textdate):
    """returns date in datetime format. Input format XX minutes ago, XX hours ago, Mon DD, YYYY, hh:mm"""
    try:
        if textdate[-3:] == 'ago':
            if textdate.find('hour') != -1:
                hours = textdate[:2].strip()
                return datetime.now() - timedelta(hours=int(hours))
            elif textdate.find('minute') != -1:
                minutes = textdate[:2].strip()
                return datetime.now() - timedelta(hours=int(minutes))
        else:
            # replace("24:", "00:") because on web-site they have formate 24:21
            return datetime.strptime(textdate.replace("24:", "00:"), '%b %d, %Y, %H:%M')
    except ValueError:
        raise ValueError("Problem with date-time convertion")
        # return datetime.now()


def set_technical_period(url):
    """
    makes TECHNICAL_URL page show Monthly recommendations.
    :return:
    """
    service = Service(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.get(url)
    driver.implicitly_wait(5)
    time_periods_box = driver.find_element(by=By.ID, value="timePeriodsWidget")
    monthly_but = time_periods_box.find_element("xpath", "//*[contains(text(), 'Monthly')]")
    monthly_but.click()
    return driver.page_source


def get_technical(url):
    """
    srape TECHNICAL_URL page and returns pandas data frame with all techincals
    :param url: url address of page with techicals
    :return: ['Name', 'Value', 'Action'] technicals
    """
    response = set_technical_period(url)
    # response = get_response(url, HEADERS)
    soup = BeautifulSoup(response, 'html.parser')   # response.content
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
            df = pd.concat([pd.DataFrame(dc, index=[0]), df.loc[:]]).reset_index(drop=True)
    return df


def get_news(url, start, end, *, return_news=True, return_comments=True):
    """
    returns news from start to end dates
    :param url: url of first page of news
    :param start: start date
    :param end: end date
    :return: list of tuples date - news
    """
    news_page_links = get_news_pages(url, start, end)
    for link in news_page_links:
        news, comments = take_news(link, return_news, return_comments)
        output_news(news, comments)


def get_news_pages(url, start, end):
    """
    Returns list of pages from start to end date
    :param url: url of first page of news
    :param start: start date of news scrapping
    :param end: end date of news scrapping
    :return: list of links to news pages from start to end date
    """
    summary_url = url
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


def get_news_comment(soup):
    comments_parent = soup.find(class_="js-comments-wrapper commentsWrapper")
    df = pd.DataFrame(columns=['id', 'news_id', 'parent_id', 'username',  'comment_text', 'postdate', 'url'])
    id_ = 1
    for comment in comments_parent.findChildren(class_='comment js-comment', recursive=False):
        comment_body = comment.find(class_="commentBody")
        username = comment_body.find(class_="commentUsername").text
        postdate_text = comment_body.find(class_="js-date").get("comment-date")
        postdate = datetime.strptime(postdate_text.replace(" 24:", " 00:"), '%Y-%m-%d %H:%M:%S')
        comment_text = comment.find(class_="js-text-wrapper commentText")
        text = comment_text.find(class_="js-text").text
        dc = {'id': id_, 'parent_id': np.NaN, 'username': username, 'postdate': postdate,
              'comment_text': text}
        parent_id = id_
        id_ += 1
        df = pd.concat([pd.DataFrame(dc, index=[0]), df.loc[:]]).reset_index(drop=True)

        for subcomment in comment.findChildren(class_='commentReply js-comment js-comment-reply', recursive=False):
            comment_body = subcomment.find(class_="commentBody js-content")
            username = comment_body.find(class_="commentUsername").text
            postdate_text = comment_body.find(class_="js-date").get("comment-date")
            postdate = datetime.strptime(postdate_text.replace(" 24:", " 00:"), '%Y-%m-%d %H:%M:%S')
            comment_text = subcomment.find(class_="js-text-wrapper commentText")
            text = comment_text.find(class_="js-text").text
            dc = {'id': id_, 'parent_id': parent_id, 'username': username, 'postdate': postdate,
                  'comment_text': text}
            id_ += 1
            df = pd.concat([pd.DataFrame(dc, index=[0]), df.loc[:]]).reset_index(drop=True)
    return df


def take_news(links, return_news, return_comments):
    """
    take single news text by link
    :param return_news: return or not news, boolean
    :param return_comments: return or not comments to news, boolean
    :param links: url to news
    :return: news
    """
    link = links
    # news = []
    # for link in links:
    #response = get_response(link, HEADERS)
    logging.info("news scraping started, url = %s", link)
    service = Service(executable_path=ChromeDriverManager().install())
    logging.debug("Service installed")
    driver = webdriver.Chrome(service=service)
    logging.debug("Driver launched")
    driver.get(link)
    logging.info("Page %s loaded", link)
    driver.implicitly_wait(5)
    response = driver.page_source

    soup = BeautifulSoup(response, 'html.parser')
    if return_news:
        title = soup.find(class_="articleHeader").text
        news_section = soup.find(class_="WYSIWYG articlePage")
        author = ''
        news_text = ''
        for parts in news_section.findChildren("p"):
            if author == '':
                author = parts.text
            else:
                news_text += parts.text + '\n'
        news_text = news_text[:-1]

        if re.search('^By ', author):
            author = author[3:]

        date = soup.find(class_="contentSectionDetails").select_one('span').text
        news = {'date': date, 'author': author, 'title': title, 'text': news_text}
    if return_comments:
        comments = get_news_comment(soup)
    return news, comments


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


def output_news(news, comments):
    """
    print, print to file,.. news
    :param news: dict of items connected to news (date, text,...)
    :return: nothing
    """
    print(f"\n date: {news['date']}, {news['author']}, {news['title']} \n text: \n {news['text']}")
    if comments.shape[0] > 0:
        print("\t", comments)


def main():
    logging.basicConfig(filename='Rate_scrapping.log',
        format='%(asctime)s-%(levelname)s+++FILE:%(filename)s-FUNC:%(funcName)s-LINE:%(lineno)d-%(message)s',
                        level=logging.INFO)
    #t = get_forum('https://www.investing.com/currencies/usd-chf-commentary', datetime(2022,6,1), datetime(2022,8,13))
    command_parser()



def valid_date(s):
    """
    supporting function to resolve if type is datetime or not in command line args
    """
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "not a valid date: {0!r}".format(s)
        raise argparse.ArgumentTypeError(msg)


def command_parser():
    """
    parser usage: "technical [url to technical page=TECHNICAL_URL]","news date_from [date_to=datetime.today()]"
    :return: print of result
    """
    parser = argparse.ArgumentParser(description='parsing data options')
    FUNCTION_MAP = {'news': get_news,
                    'technical': get_technical,
                    'forum': get_forum}
    parser.add_argument('operation', nargs="?", type=str, choices=FUNCTION_MAP.keys())

    args, sub_args = parser.parse_known_args()
    if args.operation == "technical":
        parser = argparse.ArgumentParser()
        parser.add_argument('link', nargs="?", type=str, default=TECHNICAL_URL)
        args = parser.parse_args(sub_args)
        print(FUNCTION_MAP["technical"](args.link))

    elif args.operation == "news":
        parser = argparse.ArgumentParser()
        parser.add_argument('url', type=str)
        parser.add_argument('date_from', type=valid_date)
        parser.add_argument('date_to', nargs="?", type=valid_date, default=datetime.today())
        args = parser.parse_args(sub_args)
        FUNCTION_MAP["news"](args.url, args.date_from, args.date_to)

    elif args.operation == "forum":
        parser = argparse.ArgumentParser()
        parser.add_argument('url', type=str)
        parser.add_argument('date_from', type=valid_date)
        parser.add_argument('date_to', nargs="?", type=valid_date, default=datetime.today())
        args = parser.parse_args(sub_args)
        t = FUNCTION_MAP["forum"](args.url, args.date_from, args.date_to)
        t.to_csv("output.csv")

main()
