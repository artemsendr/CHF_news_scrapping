import re
import pytz
import logging

import sys
import argparse
import pymysql
import numpy as np
from bs4 import BeautifulSoup
# import grequests
import requests
from datetime import datetime, timedelta, timezone
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

import conf as cfg

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
#FORUM_URL = 'https://www.investing.com/currencies/usd-chf-commentary/'

def get_rate(start_date, end_date, pair):
    """
    gets information about pair rate within start to end period from ecb web site
    :param pair: currency pair str
    :param start_date: start date in yyyy-mm-dd format
    :param end_date: end date in yyyy-mm-dd format
    :return: pandas dataframe date-rate
    """
    symbol = pair[-3:]
    base = pair[:3]
    url = 'https://api.exchangerate.host/timeseries?start_date=' + start_date + '&end_date=' + end_date + \
          '&symbols=' + symbol + '&base=' + base + '&source=ecb'
    response = requests.get(url)
    data = response.json()

    df = pd.DataFrame(columns=['date', 'rate'])

    for date, rate in data['rates'].items():
        rate_str = list(rate.values())[0]
        rate = float(rate_str)
        dc = {'date': date, 'rate': rate}
        df = pd.concat([pd.DataFrame(dc, index=[0]), df.loc[:]]).reset_index(drop=True)
    return df


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
    df = pd.DataFrame(columns=['id', 'instrument_id', 'parent_id', 'username', 'postdate', 'comment_text'])
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
            # comment = comments.find(class_='comment_comment-wrapper__hJ8sd')
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
            subcomment_tree = comment.find(
                class_="list_list--underline__dWxSt discussion_replies-wrapper__3sWFn").children
            dc = {'id': id_, 'instrument_id': '', 'parent_id': None, 'username': username, 'postdate': postdate,
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
                dc = {'id': id_, 'instrument_id': '', 'parent_id': parent_id, 'username': username,
                      'postdate': postdate,
                      'comment_text': comment_text}
                id_ += 1
                df = pd.concat([pd.DataFrame(dc, index=[0]), df.loc[:]]).reset_index(drop=True)
        page_number += 1
        purl = url + "/" + str(page_number)
    logging.info("forum scraping started, url = %s", url)
    return df


def db_insert_forum(df_forum, pair, cursor, cnx):
    """
    check if exist and if not insert forum to DB
    :param df_forum pandas dataframe columns = ['id', 'instrument_id', 'parent_id', 'username', 'postdate', 'comment_text']
    :param pair: currency pair in format USDRUB
    :param cursor: connection
    :param cnx: cursor to connection
    :return: nothing
    """
    # get last id from forum table
    query = "SELECT max(id) FROM forum"
    try:
        cursor.execute(query)
        last_index = cursor.fetchone()
    except Exception as e:
        logging.error("Error when selecting from forum")
        raise RuntimeError("Error when selecting from forum", e)
    if last_index[0] is None:
        add_index = 0
    else:
        add_index = last_index[0]
    # add this index to dummy id's in the dataframe
    df_forum['id'] += add_index
    df_forum['parent_id'] += add_index
    df_forum.loc[pd.isnull(df_forum['parent_id']), 'parent_id'] = None

    instrument_id = db_insert_check_instrument(pair, cursor=cursor, cnx=cnx)

    # split to head comments and comments to comments (in order to start from head ones to keep relations)
    main_comments = df_forum[pd.isnull(df_forum['parent_id'])]
    sub_comments = df_forum[pd.notnull(df_forum['parent_id'])]
    min_date = main_comments['postdate'].min(axis=0)
    max_date = main_comments['postdate'].max(axis=0)

    data_main = main_comments.to_dict('records')
    data_sub = sub_comments.to_dict('records')

    # insert data if not exists
    query = """INSERT INTO forum (id, instrument_id, parent_id, username, post_date, comment_text)
               SELECT %(id)s, """ + str(instrument_id) + """, %(parent_id)s, %(username)s, %(postdate)s, %(comment_text)s
               WHERE NOT EXISTS (SELECT 1 FROM forum 
                                 WHERE post_date = %(postdate)s and username = %(username)s and comment_text = %(comment_text)s
                                  and instrument_id = """ + str(instrument_id) + ")"

    try:
        cursor.executemany(query, data_main)
        cnx.commit()
        cursor.executemany(query, data_sub)
        cnx.commit()
        logging.info("Forum for %s have been added (if didn't exist) to forum table for period %s - %s" % (pair,
                                                                                                           min_date,
                                                                                                           max_date))
    except pymysql.err.OperationalError as e:
        logging.error("Error when inserting to forum, Check query")
        raise RuntimeError("Error when inserting to forum, Check queries", e)
    except Exception as e:
        logging.error("Error when inserting to forum")
        raise RuntimeError("Error when inserting to forum", e)


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
    soup = BeautifulSoup(response, 'html.parser')  # response.content
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
    :param return_comments: do you need to return comments Bool
    :param return_news: do you need to return news Bool
    :param url: url of first page of news
    :param start: start date
    :param end: end date
    :return: tuple of dataframes: news and comments to news (optionally empty)
    """
    logging.info("news scraping started, url = %s", url)
    df_news = pd.DataFrame(columns=['news_text', 'title', 'date', 'author', 'url'])
    df_news_comments = pd.DataFrame(columns=['id', 'news_id', 'parent_id',
                                             'username', 'comment_text', 'postdate', 'url'])
    news_page_links = get_news_pages(url, start, end)
    for link in news_page_links:
        news, comments = take_news(link, return_news, return_comments)
        if return_news and news is not None:
            news['url'] = link
            df_news = pd.concat([pd.DataFrame(news, index=[0]), df_news.loc[:]]).reset_index(drop=True)
        if return_comments and comments is not None:
            comments.loc['url'] = link
            df_news_comments = pd.concat([comments.loc[:], df_news_comments.loc[:]]).reset_index(drop=True)
        # output_news(news, comments)

    return df_news, df_news_comments


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
        news_part = soup.find(lambda tag: tag.name == 'div' and tag.get('class') == ['mediumTitle1'])
        news_items = news_part.findAll(class_="articleDetails")
        for news in news_items:
            date_scope = news.find(class_="date").text
            date = date_scope.replace(u'\xa0', "")
            date = date.strip("- ")
            try:
                date_news = datetime.strptime(date, '%b %d, %Y')
            except Exception:
                logging.error("Error of converting %s to date format" % date)
                date_news = datetime.combine(datetime.today(), datetime.min.time())
                # print("some minor errors occured during the scrapping, look the log")
            if start <= date_news <= end:
                url = news.parent.find("a").get('href')
                news_links.append(SITE_URL + url)
            elif date_news < start:
                break_condition = False
                break
        # go to next page
        page_number += 1
        summary_url = NEWS_URL + str(page_number) ## TODO: delete NEWS_URL
    return news_links


def get_news_comment(soup):
    comments_parent = soup.find(class_="js-comments-wrapper commentsWrapper")
    df = pd.DataFrame(columns=['id', 'news_id', 'parent_id', 'username', 'comment_text', 'postdate', 'url'])
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
    logging.info("news scraping started, url = %s", link)
    service = Service(executable_path=ChromeDriverManager().install())
    logging.debug("Service installed")
    driver = webdriver.Chrome(service=service)
    logging.debug("Driver launched")
    driver.get(link)
    logging.info("Page %s loaded", link)
    driver.implicitly_wait(1)
    response = driver.page_source

    soup = BeautifulSoup(response, 'html.parser')
    if return_news:
        try:
            title = soup.find(class_="articleHeader").text
            news_section = soup.find(class_="WYSIWYG articlePage")
        except Exception:
            logging.error("Error while scrapping %s" % link)
            return None, None
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
        if date.find("ago") != -1:
            date = re.search("\((.+?)\)", date).group(1)
        if date.find("ET"):
            est = pytz.timezone('US/Eastern')
            date = datetime.strptime(date[:-3], '%b %d, %Y %I:%M%p')
            date = est.localize(date).astimezone()
        else:
            date = datetime.strptime(date[:-3], '%b %d, %Y %I:%M%p')
        news = {'date': date, 'author': author, 'title': title, 'news_text': news_text}
    else:
        news = None
    if return_comments:
        comments = get_news_comment(soup)
    else:
        comments = None
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


def setup_connection(db_name=DB_NAME):
    """setup connection to local server to db_name database
    """
    try:
        cnx = pymysql.connect(host=cfg.HOST,
                              user=cfg.USER,
                              password=cfg.PASSWORD,
                              database=cfg.DB_NAME)
        logging.info("connection set up")
    except Exception:
        logging.error("Error during connection set up")
        raise ConnectionError("Error during connection to DB")
    cursor = cnx.cursor()
    return cnx, cursor


def db_insert_check_instrument(pair, cursor, cnx):
    """
    Checking if pair exist in DB, in case no - inserts
    :param cnx: connection
    :param cursor: cursor to connection
    :param pair: currency pair in format USDRUB (str)
    :return: instrument_id of pair
    """
    query = """SELECT id FROM instruments WHERE instrument_name = '%s'""" % pair
    try:
        cursor.execute(query)
        instrument_id = cursor.fetchone()
    except pymysql.err.OperationalError as e:
        raise RuntimeError("Error when inserting to instruments, Check query", e)
    except Exception as e:
        raise RuntimeError("Error when inserting to instruments", e)

    if instrument_id is None:
        query = """INSERT INTO instruments (instrument_name)
                   VALUES ('%s')""" % pair
        query_s = """SELECT id FROM instruments WHERE instrument_name = '%s'""" % pair
        try:
            cursor.execute(query)
            cnx.commit()
            logging.info("Instrument %s has been successfully added to instruments table" % instrument_id)
            cursor.execute(query_s)
            instrument_id = cursor.fetchone()
        except pymysql.err.OperationalError as e:
            logging.error("Error when inserting to instruments, Check query")
            raise RuntimeError("Error when inserting to instruments, Check queries", e)
        except Exception as e:
            logging.error("Error when inserting to instruments")
            raise RuntimeError("Error when inserting to instruments", e)
    return instrument_id[0]


def db_write_rates(cnx, cursor, pair, df_rates):
    """
    write currency rate to db (only new ones).
    :param cnx: connection
    :param cursor: cursor to connection
    :param pair: currency pair name (format USDCFH)
    :param df_rates: data frame with dates and rates
    :return: nothing
    """
    instrument_id = db_insert_check_instrument(pair, cursor=cursor, cnx=cnx)
    data = df_rates.to_dict('records')
    min_date = df_rates['date'].min(axis=0)
    max_date = df_rates['date'].max(axis=0)

    query = """INSERT INTO daily_rates (instrument_id, date_on, rate)
               SELECT """ + str(instrument_id) + """, %(date)s, %(rate)s
               WHERE NOT EXISTS (SELECT 1 FROM daily_rates 
                                 WHERE date_on = %(date)s and instrument_id = """ + str(instrument_id) + ")"
    try:
        cursor.executemany(query, data)
        cnx.commit()
        logging.info("Rates for %s have been added (if didn't exist) to daily_rates for period %s - %s" % (pair,
                                                                                                           min_date,
                                                                                                           max_date))
    except pymysql.err.OperationalError as e:
        logging.error("Error when inserting to daily_rates, Check query")
        raise RuntimeError("Error when inserting to daily_rates, Check queries", e)
    except Exception as e:
        logging.error("Error when inserting to daily_rates")
        raise RuntimeError("Error when inserting to daily_rates", e)


def output_news(news, comments):
    """
    print, print to file,.. news
    :param comments: comments to output
    :param news: dict of items connected to news (date, text,...)
    :return: nothing
    """
    print(f"\n date: {news['date']}, {news['author']}, {news['title']} \n text: \n {news['news_text']}")
    if comments.shape[0] > 0:
        print("\t", comments)


def write_news_db(cnx, cursor, pair, df_news):
    """
    write news to db (only new ones).
    :param cnx: connection
    :param cursor: cursor to connection
    :param pair: currency pair name (format USDCFH)
    :param df_news: data frame with dates and news
    :return: nothing
    """
    instrument_id = db_insert_check_instrument(pair, cursor=cursor, cnx=cnx)
    query_news = """INSERT INTO news (news_text, title, date_on, author, url)
                    SELECT %(news_text)s, %(title)s, %(date)s, %(author)s, %(url)s
                    WHERE NOT EXISTS (SELECT 1 FROM news 
                                      WHERE  url = %(url)s)    
                    """
    # 'id', 'news_text', 'title', 'date', 'author', 'url'
    query_instr = """INSERT INTO instrument_news (instrument_id, news_id)
                     SELECT """ + str(instrument_id) + """, id
                     FROM news
                     WHERE url = %(url)s and NOT EXISTS (SELECT 1 FROM instrument_news 
                                      WHERE  news_id = (select id from news where url = %(url)s limit 1)
                                      and  instrument_id = """ + str(instrument_id) + ")"
    data_news = df_news.to_dict('records')

    try:
        cursor.executemany(query_news, data_news)
        cnx.commit()
        cursor.executemany(query_instr, data_news)
        cnx.commit()
    except pymysql.err.OperationalError as e:
        logging.error("Error when inserting to news, Check query")
        raise RuntimeError("Error when inserting to news, Check queries", e)
    except Exception as e:
        logging.error("Error when inserting to news")
        raise RuntimeError("Error when inserting to news", e)


def scrape_all(pair, start_date, end_date):
    """
    scrape data for pair from forum, news, rates
    :param pair: pair: currency pair name (format USDCFH)
    :param start_date: datetime only!
    :param end_date: datetime only!
    :return: nothing
    """
    cur1 = pair[:3]
    cur2 = pair[-3:]
    url_news = "https://www.investing.com/currencies/" + cur1.lower() + '-' + cur2.lower() + '-news'
    url_forum = "https://www.investing.com/currencies/" + cur1.lower() + '-' + cur2.lower() + '-commentary'
    cnx, cursor = setup_connection(db_name=DB_NAME)
    df_news, df_comments = get_news(url_news, start_date, end_date)
    write_news_db(cnx, cursor, pair, df_news)
    df = get_forum(url_forum, start_date, end_date)
    db_insert_forum(df, pair, cursor, cnx)
    df = get_rate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), pair)
    db_write_rates(cnx, cursor, pair, df)
    cnx.close()
    cursor.close()


def main():
    logging.basicConfig(filename='Rate_scrapping.log',
                        format='%(asctime)s-%(levelname)s+++FILE:%(filename)s-FUNC:%(funcName)s-LINE:%(lineno)d-%(message)s',
                        level=logging.INFO)
    command_parser()
    print(sys.exc_info()[2])


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
                    'forum': get_forum,
                    'all': scrape_all}
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
        parser.add_argument('date_to', nargs="?", type=valid_date, default=datetime.now())
        args = parser.parse_args(sub_args)
        a, b = FUNCTION_MAP["news"](args.url, args.date_from, args.date_to)
        print(a)
        print(b)

    elif args.operation == "forum":
        parser = argparse.ArgumentParser()
        parser.add_argument('url', type=str)
        parser.add_argument('date_from', type=valid_date)
        parser.add_argument('date_to', nargs="?", type=valid_date, default=datetime.now())
        args = parser.parse_args(sub_args)
        t = FUNCTION_MAP["forum"](args.url, args.date_from, args.date_to)
        t.to_csv("output.csv")
    elif args.operation == "all":
        parser = argparse.ArgumentParser()
        parser.add_argument('pair', type=str)
        parser.add_argument('date_from', type=valid_date)
        parser.add_argument('date_to', nargs="?", type=valid_date, default=datetime.now())
        args = parser.parse_args(sub_args)
        FUNCTION_MAP["all"](args.pair, args.date_from, args.date_to)
        print("SUCCESS")


main()
