#!/usr/bin/python2.6
# -*- coding: utf-8 -*-

import os
import sys
import io
import datetime
import re
import json
import logging
import threading
from html.parser import HTMLParser
# ----
# thrid-part
# ----
import requests
# import xmltodict
from six.moves import queue as Queue
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf8')

CONFS = {
    # 并发线程数
    'THREADS': 10,
    'REQUEST': {
        # 资源URL
        # type
        # - text
        # - photo
        # - quote
        # - link
        # - chat
        # - audio
        # - video
        # 'URL': 'http://%(site)s.tumblr.com/api/read?type=%(type)s&num=%(num)d&start=%(start)d',
        # https://www.tumblr.com/svc/indash_blog?tumblelog_name_or_id=hephestos&post_id=&limit=10&offset=31&should_bypass_safemode=false&should_bypass_tagfiltering=false
        # http://hephestos.tumblr.com/api/read?type=photo&num=50&start=0
        'URL': 'http://{0}.tumblr.com/api/read?type={1}&num={2}&start={3}',
        # 设置请求超时时间
        'TIMEOUT': 10,
        # 尝试次数
        'RETRY': 5,
        # 分页请求的起始点
        'OFFSET': 0,
        # 每页请求个数
        'LIMIT': 50,
        # 是否下载图片
        'IS_DOWNLOAD_IMG': True,
        # 是否下载视频
        'IS_DOWNLOAD_VIDEO': True,
        # 是否下载文本
        'IS_DOWNLOAD_TEXT': True,
        # 图片是否根据Slug划分子目录
        'IS_PHOTO_SLUG_FOLDER': False,
    },
    'LOG': {
        # 日志目录
        'PATH': 'logs',
        # 强制帖子记录[post文件已存在也需要写入记录]
        'FORCE_POSTS_LOG': False
    }
}

logger = None


# ------------------------------------------------------------------------------
# switch
# This class provides the functionality we want. You only need to look at
# this if you want to know how this works. It only needs to be defined
# once, no need to muck around with its internals.
# ------------------------------------------------------------------------------
class Switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args: # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False


# ------------------------------------------------------------------------------
# ThreadingLock
# ------------------------------------------------------------------------------
def synchronized(func):
    func.__lock__ = threading.Lock()

    def synced_func(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)

    return synced_func


# ------------------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------------------
class Logger(logging.Manager):
    instances = {}

    @synchronized
    def getLogger(self, name='', **kwargs):
        logger_name = name

        logger = None

        # FileHandler
        handler = None
        for case in Switch(name):
            if case('') or case('common'):
                logger_name = 'common'
                log_filename = "logs/common.log"
                break
            if case('site'):
                logger_name = 'site_%s' % kwargs['site']
                log_filename = "logs/%(site)s.log" % {
                    'site': kwargs['site']
                }
                break
            if case('post'):
                logger_name = '%(site)s_%(media_type)s_posts' % {
                    'site': kwargs['site'],
                    'media_type': kwargs['media_type']
                }
                log_filename = "blogs/%(site)s/%(site)s_%(media_type)s_posts.log" % {
                    'site': kwargs['site'],
                    'media_type': kwargs['media_type']
                }
                break
            if case('updated'):
                logger_name = 'updated_%s' % kwargs['site']
                log_filename = "blogs/%(site)s/%(site)s_updated.log" % {
                    'site': kwargs['site']
                }
                break

        if logger_name in Logger.instances:
            return Logger.instances[logger_name]

        logger = super(Logger, self).getLogger(logger_name)
        handler = logging.FileHandler(log_filename)
        if handler is None:
            log_filename = "logs/%s.log" % site
            handler = logging.FileHandler(log_filename)

        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s][Line:%(lineno)d] %(message)s \n')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # StreamHandler
        console = logging.StreamHandler()
        logger.addHandler(console)

        # CommonSet
        logger.setLevel(level = logging.INFO)

        Logger.instances[logger_name] = logger
        return Logger.instances[logger_name]


# ------------------------------------------------------------------------------
# Download Worker
# ------------------------------------------------------------------------------
class TumblrHtmlParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.__text = []

    def handle_data(self, data):
        text = data.strip()
        if len(text) > 0:
            text = re.sub('[ \t\r\n]+', ' ', text)
            self.__text.append(text + ' ')

    def handle_starttag(self, tag, attrs):
        if tag == 'p':
            self.__text.append('\n\n')
        elif tag == 'br':
            self.__text.append('\n')

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self.__text.append('\n\n')

    def text(self):
        return ''.join(self.__text).strip()


# ------------------------------------------------------------------------------
# Download Worker
# ------------------------------------------------------------------------------
class DownloadWorker(threading.Thread):
    def __init__(self, queue, proxies=None, logger=None):
        threading.Thread.__init__(self)
        self.queue = queue
        self.proxies = proxies
        self.logger = logger

    def run(self):
        while True:
            site, media_type, post, download_folder = self.queue.get()
            self.log = self.logger.getLogger('site', site=site)
            self.download(site, media_type, post, download_folder)
            self.queue.task_done()
            pass

    def download(self, site, media_type, post, download_folder):
        media_list = self._handle_media_list(media_type, post)
        print('[%s-PostSlug]%s' % (site, post['slug']))
        print(media_list)

        sub_folder = ""
        if CONFS['REQUEST']['IS_PHOTO_SLUG_FOLDER'] and media_type == "photo" and post['slug']:
            sub_folder = post['slug']

        if media_type == "photo" or media_type == "video":
            for media in media_list:
                self._download(site, media_type, media, download_folder, sub_folder)
                pass
        if media_type == "text":
            self._download_text(site, media_type, post, media_list, download_folder)

    def _handle_media_list(self, media_type, post):
        media_list = []
        if media_type == "photo":
            # 多种采集模式
            if post.find('regular-body'):
                regularBodyObj = post.find('regular-body')
                # print(regularBody.string)
                bodyObj = BeautifulSoup(regularBodyObj.string, 'html.parser')
                imgs = bodyObj.find_all('img')
                if imgs:
                    for img in imgs:
                        media_list.append(img['src'])
                        pass
            if post.find('photoset'):
                photosetObj = post.find('photoset')
                if photosetObj:
                    for photo in photosetObj.contents:
                        for photo_url in photo.contents:
                            # 取第一章图[尺寸最大], 其他均为小尺寸图片
                            media_list.append(photo_url.string)
                            break
                        pass
            elif post.find('photo-url'):
                photoUrlObj = post.find('photo-url')
                if photoUrlObj:
                    for photo_url in photoUrlObj.contents:
                        # 取第一章图[尺寸最大], 其他均为小尺寸图片
                        media_list.append(photo_url.string)
                        break
        elif media_type == "video":
            # videoPlayerText = post["video-player"][1]["#text"]
            if post.find('video-player'):
                # 查找第一个
                videoPlayerText = post.find('video-player').string
                if videoPlayerText:
                    hd_pattern = re.compile(r'.*"hdUrl":("([^\s,]*)"|false),')
                    hd_match = hd_pattern.match(videoPlayerText)
                    try:
                        if hd_match is not None and hd_match.group(1) != 'false':
                            media_list.append(hd_match.group(2).replace('\\', ''))
                    except IndexError:
                        pass
                    pattern = re.compile(r'.*src="(\S*)" ', re.DOTALL)
                    match = pattern.match(videoPlayerText)
                    if match is not None:
                        try:
                            media_list.append(match.group(1))
                        except IndexError:
                            # return None
                            pass
            pass
        elif media_type == "text":
            reg_remove_html_tag = re.compile("<[^>]*>")
            reg_remove_empty_string = re.compile("^\s+|\s+$")
            # 多种采集模式
            if post.find('regular-body'):
                regularBodyObj = post.find('regular-body')
                # print(regularBody.string)
                bodyObj = BeautifulSoup(regularBodyObj.string, 'html.parser')
                # blockquotes = bodyObj.find_all('blockquote')
                # for blockquote in blockquotes:
                #     media_list.append(reg_remove_html_tag.sub('', blockquote.prettify()))
                #     pass

                text = bodyObj.prettify()
                # try:
                #     parser = TumblrHtmlParser()
                #     parser.feed(text)
                #     parser.close()
                #     text = parser.text()
                # except:
                #     print('TumblrHtmlParser failed, try BeautifulSoup prettify')
                #     text = reg_remove_html_tag.sub('', text)
                #     text = reg_remove_empty_string.sub('', text)
                #     pass

                if text:
                    media_list.append(text)
        return media_list

    def _download(self, site, media_type, media_url, download_folder, sub_folder=""):
        logPost = self.logger.getLogger('post', site=site, media_type=media_type)

        # get MediaName
        if media_type == "photo":
            media_name = media_url.split("/")[-1].split("?")[0]
        elif media_type == "video":
            media_name = media_url.split("/")[-1].split("?")[0]
            if not media_name.startswith("tumblr"):
                media_name = "_".join([media_url.split("/")[-2], media_name])
            media_name += ".mp4"

        if sub_folder:
            download_folder = os.path.join(download_folder, sub_folder)
            if not os.path.isdir(download_folder):
                os.makedirs(download_folder)

        file_path = os.path.join(download_folder, media_name)

        print(file_path)

        if not os.path.isfile(file_path):
            logPost.info(media_url)

            print("Downloading %s from %s\n" % (media_name, media_url))
            retry_times = 0
            while retry_times < CONFS['REQUEST']['RETRY']:
                try:
                    resp = requests.get(media_url,
                                        stream=True,
                                        proxies=self.proxies,
                                        timeout=CONFS['REQUEST']['TIMEOUT'])
                    with open(file_path, 'wb') as fh:
                        for chunk in resp.iter_content(chunk_size=1024):
                            fh.write(chunk)
                    break
                except:
                    # try again
                    pass
                retry_times += 1
            else:
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                print("Failed to retrieve %s from %s.\n" % (media_type, media_url))
        else:
            if CONFS['LOG']['FORCE_POSTS_LOG']:
                logPost.info(media_url)
        pass

    def _download_text(self, site, media_type, post, media_list, download_folder):
        logPost = self.logger.getLogger('post', site=site, media_type=media_type)

        text_name = '%s.txt' % post['slug']
        file_path = os.path.join(download_folder, text_name)
        if not os.path.isfile(file_path):
            print("Write %s\n" % (text_name))

            with open(file_path, 'w+', encoding='utf-8') as f:
                f.writelines(media_list)
            pass
        else:
            if CONFS['LOG']['FORCE_POSTS_LOG']:
                logPost.info(post['url'])
        pass


# ------------------------------------------------------------------------------
# Crawler Scheduler
# ------------------------------------------------------------------------------
class CrawlerScheduler(object):
    def __init__(self, sites, proxies=None, logger=None):
        self.sites = sites
        self.proxies = proxies
        self.logger = logger
        self.queue = Queue.Queue()
        self.scheduling()

    def scheduling(self):
        # 创建工作线程
        for x in range(CONFS['THREADS']):
            worker = DownloadWorker(self.queue, proxies=self.proxies, logger=self.logger)
            #设置daemon属性，保证主线程在任何情况下可以退出
            worker.daemon = True
            worker.start()

        for site in self.sites:
            self.log = self.logger.getLogger('site', site=site)
            self.log.info('starting download %s media ...' % site)
            if CONFS['REQUEST']['IS_DOWNLOAD_IMG']:
                self.download_photos(site)
            if CONFS['REQUEST']['IS_DOWNLOAD_VIDEO']:
                self.download_videos(site)
            if CONFS['REQUEST']['IS_DOWNLOAD_TEXT']:
                self.download_text(site)

    def download_videos(self, site):
        media_type = 'video'

        # Mkdir
        current_folder = os.getcwd()
        download_folder = os.path.join(current_folder, "blogs", site, media_type)
        if not os.path.isdir(download_folder):
            os.makedirs(download_folder)
        self.download_folder = download_folder

        self._download_media(site, media_type, CONFS['REQUEST']['OFFSET'])
        # 等待queue处理完一个用户的所有请求任务项
        self.queue.join()
        # 写入更新报告
        logUpdated = self.logger.getLogger('updated', site=site)
        logUpdated.info('[%s] updated done.' % media_type)

        self.log.info("视频下载完成 %s" % site)

    def download_photos(self, site):
        media_type = 'photo'

        # Mkdir
        current_folder = os.getcwd()
        download_folder = os.path.join(current_folder, "blogs", site, media_type)
        if not os.path.isdir(download_folder):
            os.makedirs(download_folder)
        self.download_folder = download_folder

        self._download_media(site, media_type, CONFS['REQUEST']['OFFSET'])
         # 等待queue处理完一个用户的所有请求任务项
        self.queue.join()
        # 写入更新报告
        logUpdated = self.logger.getLogger('updated', site=site)
        logUpdated.info('[%s] updated done.' % media_type)

        self.log.info("图片下载完成 %s" % site)

    def download_text(self, site):
        media_type = 'text'

        # Mkdir
        current_folder = os.getcwd()
        download_folder = os.path.join(current_folder, "blogs", site, media_type)
        if not os.path.isdir(download_folder):
            os.makedirs(download_folder)
        self.download_folder = download_folder

        self._download_media(site, media_type, CONFS['REQUEST']['OFFSET'])
         # 等待queue处理完一个用户的所有请求任务项
        self.queue.join()
        # 写入更新报告
        logUpdated = self.logger.getLogger('updated', site=site)
        logUpdated.info('[%s] updated done.' % media_type)

        self.log.info("文本下载完成 %s" % site)

    def _download_media(self, site, media_type, start):
        base_url = "http://{0}.tumblr.com/api/read?type={1}&num={2}&start={3}"
        # base_url = CONFS['REQUEST']['URL']
        start = CONFS['REQUEST']['OFFSET']
        limit = CONFS['REQUEST']['LIMIT']
        total = 0

        while True:
            try:
                media_url = base_url.format(site, media_type, limit, start)
                # media_url = base_url % {
                #     'site': site,
                #     'media_type': media_type,
                #     'start': start,
                #     'num': limit
                # }
                self.log.info('[RequestGet]starting get %s' % media_url)

                response = requests.get(
                    media_url,
                    proxies=self.proxies
                )
                # 过滤非法字符
                response_content = response.content.decode('utf-8')
                response_content = response_content.replace('', '')

                # xmltodict parse
                # rsp = xmltodict.parse(response_content)
                # posts = data["tumblr"]["posts"]["post"]
                # self.log.info('the post len is %d' % len(posts))
                # for index, post in enumerate(posts):
                #     # select the largest resolution
                #     # usually in the first element
                #     # Todo
                #     # self.queue.put((site, media_type, post, download_folder))
                #     pass

                # BeautifulSoup parse
                rsp = BeautifulSoup(response_content, 'lxml')

                posts = rsp.tumblr.posts
                total = rsp.tumblr.posts['total']
                self.log.info('current offset is %s, the post len is %d' % (start, len(posts)))

                if len(posts) == 0:
                    break

                # for post in posts.children:
                for index, post in enumerate(posts):
                    # print(index)
                    # print(post)
                    # if index != 1:
                    # print(post['id'])
                    # if post['id'] != '177695853053':
                    #     continue
                    self.queue.put((site, media_type, post, self.download_folder))
                    pass
                # print(posts)

                # if start > total:
                #     break

                start += CONFS['REQUEST']['LIMIT']
            except Exception as e:
                self.log.error('[GetMediaFail] %s' % media_url)
                print(e)
                break


# ------------------------------------------------------------------------------
# Functions
# ------------------------------------------------------------------------------

def dict_merge(dict1, dict2):
    for key, value in dict2.items():
        if type(value).__name__ == 'dict':
            dict_merge(dict1[key], dict2[key])
        else:
            dict1[key] = dict2[key]
    pass

""" Parse a JSON file
    First remove comments and then use the json module package
    Comments look like :
        // ...
    or
        /*
        ...
        */
"""
def parse_json(filename):
    comment_re = re.compile(
        '(^)?[^\S\n]*/(?:\*(.*?)\*/[^\S\n]*|/[^\n]*)($)?',
        re.DOTALL | re.MULTILINE
    )
    with open(filename, 'r') as f:
        content = ''.join(f.readlines())
        ## Looking for comments
        match = comment_re.search(content)
        while match:
            # single line comment
            content = content[:match.start()] + content[match.end():]
            match = comment_re.search(content)

        # print content
        # Return json file
        return json.loads(content)
    pass

def usage():
    print(u"未找到conf_sites.txt文件，请创建.\n"
          u"请在文件中指定Tumblr站点名，每行一个.\n"
          u"保存文件并重试.\n\n"
          u"或者直接使用命令行参数指定站点\n"
          u"例子: python tumblr-photo-video-ripper.py site1,site2")

def illegal_json_conf(filename):
    print('''
配置文件[%(filename)s]存在格式非法.
请通过配置注释了解配置项.
然后去 http://jsonlint.com/ 进行验证.
    ''' % {
        'filename': filename
    })


if __name__ == "__main__":
    # Mk Log Dir
    root_folder = os.getcwd()
    log_folder = os.path.join(root_folder, "logs")
    if not os.path.isdir(log_folder):
        os.makedirs(log_folder)

    logger = Logger(logging.root)
    # logger_common = logger.getLogger('')
    # logger_common.info('hello')
    # logger_site = logger.getLogger('site', site='test')
    # logger_site.info('hello')

    confs = None
    conf_path = 'conf.json'
    if os.path.exists(conf_path):
        try:
            default_confs = CONFS
            confs = parse_json(conf_path)
            dict_merge(CONFS, confs)
            # CONFS = {**CONFS, **confs}
            # CONFS = {}
            # CONFS.update(default_confs)
            # CONFS.update(confs)
            # CONFS = dict(CONFS.items() + confs.items())
        except Exception as e:
            print(e)
            illegal_json_conf(conf_path)
            sys.exit(1)

    proxies = None
    proxies_path = 'conf_proxies.json'
    if os.path.exists(proxies_path):
        try:
            proxies = parse_json(proxies_path)
        except:
            illegal_json_conf(proxies_path)
            sys.exit(1)

    sites = []
    if len(sys.argv) >= 2:
        sites = sys.argv[1].split(",")
    sites_path = 'conf_sites.txt'
    if os.path.exists(sites_path):
        # check conf_sites.txt
        if os.path.exists(sites_path):
            with open(sites_path, "r") as _file:
                for line in _file.readlines():
                    site = line.rstrip().lstrip().strip('\n')
                    sites.append(site)

    sites = list(set(sites))

    if len(sites) == 0 or sites[0] == "":
        usage()
        sys.exit(1)

    # start site download tasks
    CrawlerScheduler(sites, proxies=proxies, logger=logger)

    pass
