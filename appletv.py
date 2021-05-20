import csv
import html
import json
import os
import re
import sys
import zlib

import backoff
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


def main():
    data = inputdata()
    if data:
        print("input rows: {}".format(len(data)), file=sys.stderr)

    csvout = csv.writer(sys.stdout)
    csvout.writerow(["id", "name", "desc", "url", "type"])
    for (id, name, desc, url, type) in crawl(data):
        csvout.writerow([id, name, desc, url, type])
        sys.stdout.flush()


def inputdata():
    if len(sys.argv) == 1:
        return {}
    elif sys.argv[1] == "-":
        file = sys.stdin
    else:
        file = open(sys.argv[1], "r")

    data = {}
    for row in csv.reader(file):
        if not row:
            break
        (id, name, desc, url, type) = row
        if id == "id":
            continue
        data[id] = (id, name, desc, url, type)

    file.close()
    return data


def crawl(data={}):
    for url in sitemap():
        m = re.match(r"https://tv.apple.com/us/movie/([^/]+/)?(umc.cmc.[0-9a-z]+)", url)
        if not m:
            continue
        id = m.group(2)

        if id in data:
            yield data[id]
            continue

        text = fetch(url)
        soup = BeautifulSoup(text, "html.parser")

        for script in soup.find_all("script", {"type": "application/ld+json"}):
            ld = json.loads(script.string)
        if not ld:
            continue

        name = html.unescape(ld["name"])
        desc = "film"

        if "datePublished" in ld:
            year = ld["datePublished"][0:4]
            desc = "{} film".format(year)

        if "director" in ld:
            director = " and ".join([html.unescape(p["name"]) for p in ld["director"]])
            desc += " directed by {}".format(director)

        type = "Q11424"

        yield (id, name, desc, url, type)


def sitemap():
    r = requests.get("https://tv.apple.com/sitemaps_tv_index_1.xml")
    r.raise_for_status()

    soup = BeautifulSoup(r.content, "lxml")

    for loc in tqdm(soup.find_all("loc"), desc="sitemaps_tv_index_1.xml"):
        r = requests.get(loc.text)
        r.raise_for_status()

        xml = zlib.decompress(r.content, 16 + zlib.MAX_WBITS)
        soup = BeautifulSoup(xml, "lxml")

        filename = os.path.basename(loc.text)
        for loc in tqdm(soup.find_all("loc"), desc=filename):
            yield loc.text


session = requests.Session()
session.headers.update(
    {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-us",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        + "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        + "Version/14.1.1 Safari/605.1.15",
    }
)


@backoff.on_exception(backoff.expo, requests.exceptions.ConnectionError, max_tries=5)
@backoff.on_exception(backoff.expo, requests.exceptions.HTTPError, max_tries=5)
@backoff.on_exception(backoff.expo, requests.exceptions.SSLError, max_tries=5)
def fetch(url):
    r = session.get(url)
    r.raise_for_status()
    return r.text


if __name__ == "__main__":
    main()
