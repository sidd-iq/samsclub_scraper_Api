import re
import os
import asyncio
from random import randint, choice
import uuid
import httpx
import logging
import random
from itertools import cycle
from fastapi import FastAPI, HTTPException
from fastapi.param_functions import Query
import chompjs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
PROXIES = []
TIMEOUT = float(os.environ.get("TIMEOUT", "10.0"))
http_client = httpx.AsyncClient(timeout=TIMEOUT)
proxy_cycle = cycle(PROXIES)
url_regex = r"https://www.samsclub.com/p/([a-zA-Z0-9-]+)/.+"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:93.0) Gecko/20100101 Firefox/93.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/93.0",
]

app = FastAPI()

def get_headers(type:str):
    headers = {"product_page":  {
    'authority': 'www.samsclub.com',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'origin': 'https://www.samsclub.com',
    'pragma': 'no-cache',
    'referer': 'https://www.samsclub.com/p/ninja-creami-breeze/P03018935?xid=hpg_carousel_rich-relevance.rr1_4',
    'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
}
    }
    return headers[type]
def extract_id_from_url(url:str):
    pattern = r"/p/(.+)/([A-Za-z0-9]+)"
    match = re.search(pattern, url)
    if match:
        product_code = match.group(2)
        logger.info("Product code: %s", product_code)
        return product_code
    else:
        logger.warning("Invalid URL: %s no ID found", url)

import random
def randomMAC():
    mac = [
        0x00,
        0x16,
        0x3E,
        randint(0x00, 0x7F),
        randint(0x00, 0xFF),
        randint(0x00, 0xFF),
    ]
    return ":".join(map(lambda x: "%02x" % x, mac))


def get_cookie():
    clock_seq = [49151, 45055]
    mac_ = randomMAC().replace(":", "")
    _pxvid_uuid = uuid.uuid1(clock_seq=choice(clock_seq))
    _pxvid = "-".join(str(_pxvid_uuid).split("-")[:-1]) + "-" + mac_

    """
        walmart id cookies rotation
        Both these cookie are part of perimeterX istself.
        These cookie contains datetime within.
    """
    _uetsid_random = str(uuid.uuid4()).split("-")[-1]
    _uetvid_random = str(uuid.uuid4()).split("-")[-1]

    _uetsid_uuid = uuid.uuid1(clock_seq=choice(clock_seq))
    _uetvid_uuid = uuid.uuid1(clock_seq=choice(clock_seq))
    _uetsid = "-".join(str(_uetsid_uuid).split("-")[:-1]) + "-" + _uetsid_random
    _uetvid = "-".join(str(_uetvid_uuid).split("-")[:-1]) + "-" + _uetvid_random
    return {"_pxvid": _pxvid, "_uetsid": _uetsid, "_uetvid": _uetvid}
async def get_product_page_data(session,url:str):
    id = extract_id_from_url(url)
    headers = get_headers("product_page")
    json_data = {
        'productIds': [
            id,
        ],
        'type': 'LARGE',
        'clubId': 4846,
    }
    response = await fetch_content(session, "https://www.samsclub.com/api/node/vivaldi/browse/v2/products", headers=headers,json=json_data,cookies=get_cookie())
    return chompjs.parse_js_object(response)


async def fetch_content(session, url, headers,json=None,params=None,cookies=None):
    try:
        if not json:
            response = await session.get(url, headers=headers,params=params,cookies=cookies)
        else:
            response = await session.post(url, headers=headers,json=json,cookies=cookies)
        if response.status_code == 200:
            content = await response.aread()  # Use response.read() for improved performance
            logger.info("Successful response for URL: %s", url)
            return content.decode("utf-8")
        elif response.status_code in (403, 429):  # Blocked status codes
            # Rotate to the next proxy if available
            proxy = next(proxy_cycle, None)
            if proxy is not None:
                http_client.proxies = {"http": proxy, "https": proxy}
                logger.warning("Blocking issue encountered for URL: %s. Trying next proxy: %s", url, proxy)
                return await fetch_content(session, url, headers,json,params)  # Retry with the new proxy
            else:
                logger.error("All proxies exhausted for URL: %s. Blocked with status code: %s", url, response.status_code)
                return f"Blocked: {response.status_code}"
        else:
            logger.error("Error encountered for URL: %s with status code: %s", url, response.status_code)
            return f"Error: {response.status_code}"
        return content
    except httpx.RequestError as e:
        logger.error("Request error encountered for URL: %s. Error: %s", url, str(e))
        return str(e)

@app.on_event("shutdown")
async def close_http_client():
    await http_client.aclose() # Close the httpx.AsyncClient on application shutdown

@app.get("/product")
async def product_page(url: str = Query(...)):
    if not re.match(url_regex, url):
        raise HTTPException(status_code=400, detail="Invalid url parameters: Only valid samsclub product URLs are allowed")

    async with httpx.AsyncClient(timeout=TIMEOUT) as session:
        product_page_data = await get_product_page_data(session,url)

        product_page_data = product_page_data.get("payload", {}).get("products", [])[0]
        # logger.info("Product page data: %s", product_page_data)
        name = product_page_data.get("descriptors", {}).get("name", "")
        short_description = product_page_data.get("descriptors", {}).get("shortDescription", "")
        Description = product_page_data.get("descriptors", {}).get("longDescription", "")
        Bullets = short_description
        Samsclub_id = product_page_data.get("skus", [None])[0].get("skuId", "")
        Product_id = product_page_data.get("skus", [None])[0].get("productId", "")
        Model_number = product_page_data.get("manufacturingInfo", {}).get("model", "")
        brand = product_page_data.get("manufacturingInfo", {}).get("brand", "")
        upc = product_page_data.get("skus", [None])[0].get("clubOffer", {}).get('itemNumber', "")
        sale_price = product_page_data.get("skus", [None])[0].get("clubOffer", {}).get("price",{}).get("finalPrice", {}).get("amount", None)
        msrp = product_page_data.get("skus", [None])[0].get("clubOffer", {}).get("price",{}).get("startPrice", {}).get("amount", None)
        price_range = {}
        currency = "USD"
        review_count = product_page_data.get("reviewsAndRatings",{}).get("numReviews",0)
        avg_rating = product_page_data.get("reviewsAndRatings",{}).get("avgRating",0)
        specification = product_page_data.get("manufacturingInfo",{}).get("specification",None)
        data = {
            "title": name,
            "Description": Description,
            "samsclub_id": Samsclub_id,
            "product_id": Product_id,
            "bullets": Bullets,
            "model_number": Model_number,
            "upc": upc,
            "brand": brand,
            "msrp": float(msrp) if msrp else None,
            "sale_price": float(sale_price) if sale_price else None,
            "price_range": price_range,
            "currency": currency,
            "review_count": review_count,
            "avg_rating": avg_rating,
            "specification": specification,
            "shipped_by": "samsclub.com",
            "sold_by": "samsclub.com",
        }
        return data




