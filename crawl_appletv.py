import csv
import html
import json
import os
import re
import zlib

import backoff
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

catalogs = ["4453"]


def main():
    data = {}
    files = {}
    csvwriters = {}

    for catalog_id in catalogs:
        with open("{}.csv".format(catalog_id), "r") as f:
            for (id, name, desc, url, type) in csv.reader(f):
                if id == "id":
                    continue
                data[id] = (catalog_id, id, name, desc, url, type)

    for catalog_id in catalogs:
        files[catalog_id] = open("{}.csv".format(catalog_id), "w")
        csvwriters[catalog_id] = csv.writer(files[catalog_id])
        csvwriters[catalog_id].writerow(["id", "name", "desc", "url", "type"])

    for (catalog_id, id, name, desc, url, type) in crawl(data):
        csvwriters[catalog_id].writerow([id, name, desc, url, type])

    for catalog_id in catalogs:
        files[catalog_id].close()


def crawl(data={}):
    for url in sitemap():
        m = re.match(
            r"https://tv.apple.com/us/(movie)/([^/]+/)?(umc.cmc.[0-9a-z]+)", url
        )
        if not m:
            continue
        type = m.group(1)
        id = m.group(3)

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

        yield ("4453", id, name, desc, url, type)


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
