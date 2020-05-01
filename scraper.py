#!/usr/bin/env python3
import requests
import json
import sys
import os
import hashlib
import base64
import re


class Scraper:
    def __init__(self, url: str, keep_names: bool):
        self.__url = url
        self.__keep_names = keep_names

        self.__board, self.__thread_id = self.__parse_url(url)
        self.__destination = os.path.join(self.__board, self.__thread_id)

        if self.__keep_names:
            self.downloaded_files = []

        if not os.path.exists(self.__destination):
            os.makedirs(self.__destination)
        
        self.bar_length = 20

        self.__get_thread()

    def __parse_url(self, url: str) -> tuple:
        url = url.split("/") # ['https:', '', 'boards.4channel.org', 'g', 'thread', '51971506']
        board = url[3]
        thread_id = url[5]

        return board, thread_id

    def __get_thread(self) -> None:
        response = requests.get("https://a.4cdn.org/{0}/thread/{1}.json".format(
            self.__board,
            self.__thread_id
        ))
        if len(response.text) == 0:
            raise ThreadDoesNotExist(self.__board, self.__thread_id)

        self.__thread = json.loads(response.text)

    def __get_images(self) -> None:
        posts = self.__thread["posts"]
        images = [post for post in posts if "tim" in post] # isolates posts that have an attachment from ones that don't
        self.__image_total = len(images)

        for self.__image_count, image in enumerate(images):
            self.__download_image(image)
    
    def __download_image(self, image: dict) -> None:
        filename = ""

        if self.__keep_names:
            filename = image["filename"] + image["ext"]
            self.downloaded_files.append(filename)
            
            if filename in self.downloaded_files[:-1]:
                # filename_1 if there is already a file called filename
                filename = "{0}_{1}{2}".format(
                    image["filename"],
                    self.downloaded_files.count(filename)-1,
                    image["ext"]
                )
        else:
            filename = str(image["tim"]) + image["ext"]
        
        file_path = os.path.join(self.__destination, filename)

        # redownloads if file is corrupted or missing
        if os.path.exists(file_path):
            # dumb 4chan api decides to encode their md5 strings into base64
            md5 = base64.b64decode(image["md5"]).hex()

            if self.__md5check(file_path, md5):
                print("{} already exists. Skipping...".format(filename))
                return

        response = requests.get("https://i.4cdn.org/{0}/{1}".format(
            self.__board,
            str(image["tim"]) + image["ext"]
        ))

        size = int(response.headers["Content-length"])
        dl = 0
        
        try:
            with open(file_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            # TODO: Clean up progress bar because it looks bad with --keep_names flag

                            dl += len(chunk)
                            file.write(chunk)

                            progress = dl / size

                            bar_percent = int(round(progress * self.bar_length))
                            bar = '█'*bar_percent + " "*(self.bar_length - bar_percent)

                            sys.stdout.write("\r{0} of {1} {2} |{3}| {4:.2f}%".format(
                                self.__image_count + 1, # adding 1 because it starts at 0
                                self.__image_total,
                                filename,
                                bar,
                                progress * 100))
                            
                            sys.stdout.flush()
                    sys.stdout.write('\n')

        except KeyboardInterrupt:
            os.remove(file_path)
            raise KeyboardInterrupt
        finally:
            file.close()

    def __md5check(self, path: str, md5: str) -> bool:
        """ https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file """
        with open(path, 'rb') as file:
            data = file.read()
            file_md5 = hashlib.md5(data).hexdigest()
            file.close()
            return file_md5 == md5

    def Scrape(self) -> None:
        self.__get_thread()
        self.__get_images()


class InvalidThreadURL(Exception):
    def __init__(self, url: str):
        self.message = url

    def __str__(self) -> str:
        return "{} is an invalid thread URL.".format(self.message)

class ThreadDoesNotExist(Exception):
    def __init__(self, board: str, thread_id: str):
        self.board = board
        self.thread_id = thread_id

    def __str__(self) -> str:
        return "Thread with ID {} in board {} does not exist.".format(self.thread_id, self.board)

def check_url(url) -> bool:
    exp = re.compile(r"^(https:\/\/boards.4channel.org\/|https:\/\/boards.4chan.org\/)[a-z]{1,5}\/thread\/[0-9]*$")
    match = re.search(exp, url)
    return True if match else False


def main(args) -> None:
    exitcode = 0
    # check if the URLs are valid
    # inform user if not
    validURLs = []

    for url in args.URLs:
        try:
            valid = check_url(url)
        
            if valid == False:
                raise InvalidThreadURL(url)
            validURLs.append(url)
        
        except InvalidThreadURL as err:
            print(err)
            exitcode = 1
    
    threads = []
    for url in validURLs:
        try:
            threads.append(Scraper(url, args.keep_names))
        except ThreadDoesNotExist as err:
            print(err)
            exitcode = 1

    for thread in threads:
        thread.Scrape()

    exit(exitcode)


if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Scrapes images from 4chan threads using the 4chan api.",
        usage=f"{sys.argv[0]} [options] URL(s)"
    )

    parser.add_argument(
        "URLs", nargs="+",
        help="links to 4chan threads"
    )

    parser.add_argument(
        "-k", "--keep-names", action="store_true",
        help="keep original filenames, defaults to False"
    )

    # TODO: Implement setting destination path flag
    #parser.add_argument(
    #    "--path", metavar="directory",
    #    default=".",
    #    help="where to store the create the thread directories, defaults to './'"
    #)

    args = parser.parse_args()
    
    try:
        main(args)
    except KeyboardInterrupt:
        print("\nProgram Aborted.")
        exit(130)
