import os
import re
import sys
import time
import webbrowser
from binascii import hexlify
from secrets import token_bytes
from threading import Lock

import validators
from watchdog.events import RegexMatchingEventHandler
from watchdog.observers import Observer


class HtmlHandler(RegexMatchingEventHandler):
    NAME_REGEX = r'.*\.(html|htm)$'
    CONTENT_REGEX = r"<html><head><meta.*http-equiv=\"Content-Type\".*content=\"text/html.*\"/?></head><body><a.*href" \
                    r"=\".*\".*>(.*)</a></body></html>"

    def __init__(self, on_url_found=None):
        super().__init__([self.NAME_REGEX])

        if on_url_found is None:
            on_url_found = lambda *args: None
        self.__on_url_found = on_url_found

    def on_created(self, event):
        if not self.__is_correct_file(event.src_path):
            return

        url = self.__extract_url(event.src_path)
        self.__on_url_found(url)

    def __extract_url(self, path):
        with open(path) as file:
            content = "".join(file.readlines())
            test = re.compile(self.CONTENT_REGEX, re.IGNORECASE)

            url, = test.findall(content)

            return url

    def __is_correct_file(self, path):
        with open(path) as file:
            content = "".join(file.readlines())
            test = re.compile(self.CONTENT_REGEX, re.IGNORECASE)

            if not test.match(content):
                return False

            url, = test.findall(content)

            if not validators.url(url):
                return False

        return True


class LinkObserver(object):
    def __init__(self, path, handler):
        self.__path = path
        self.__event_handler = handler
        self.__event_observer = Observer()

    def start(self):
        self.__schedule()
        self.__event_observer.start()

    def stop(self):
        self.__event_observer.stop()
        self.__event_observer.join()

    def __schedule(self):
        self.__event_observer.schedule(
            self.__event_handler,
            self.__path,
            recursive=False
        )


class UrlProcessor(object):
    def __init__(self, lock, history_file_path):
        self.__lock = lock
        self.__history_file_path = history_file_path

    def process(self, url):
        webbrowser.open_new_tab(url)

        if self.__history_file_path is None:
            return

        self.__lock.acquire()
        try:
            self.__write_to_file(url)
        finally:
            self.__lock.release()

    def __write_to_file(self, data):
        temp_filename = 'temp{}'.format(str(hexlify(token_bytes(6))))

        temp_file = open(temp_filename, 'w+')
        temp_file.write('|'.join([data, str(int(time.time()))]) + '\n')

        with open(self.__history_file_path, 'r') as file:
            for line in file:
                temp_file.write('{}'.format(line))
        os.remove(self.__history_file_path)
        temp_file.close()

        os.rename(temp_filename, self.__history_file_path)


if __name__ == '__main__':
    path_to_observe = sys.argv[1] if len(sys.argv) > 1 else '.'
    history_file = sys.argv[2] if len(sys.argv) > 2 else None

    lock = Lock()
    url_processor = UrlProcessor(lock, history_file)

    html_handler = HtmlHandler(url_processor.process)
    observer = LinkObserver(path_to_observe, html_handler)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
