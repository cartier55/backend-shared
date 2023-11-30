import sys
sys.path.append('C:/Users/carte/OneDrive/Documents/Code/Coach Box/backend/')
import asyncio
import httpx
import re
import time
from pprint import pprint as pp
from logger import coach_logger

async def fetch_youtube_link(session, url, day):
    try:
        response = await session.get(url, follow_redirects=True)
        match = re.search(r'<link rel="shortlinkUrl" href="([^"]+)">', response.text)
        if match:
            return day, match.group(1)
        else:
            coach_logger.log_warning(f'[!] No YouTube link found for {day}')
            return day, 'No YouTube link found'
    except httpx.HTTPError as e:
        coach_logger.log_error(f'[-] HTTP error occurred: {e}')
        return day, 'HTTP error'
    except Exception as e:
        coach_logger.log_error(f'[-] Error occurred: {e}')
        return day, 'Error occurred'

async def fetch_youtube_links_async(deka_urls_dict):
    coach_logger.log_info("[+] Fetching YouTube links...")
    yt_links_by_day = {}

    async with httpx.AsyncClient() as client:
        tasks = [fetch_youtube_link(client, url, day) for day, url in deka_urls_dict.items()]
        results = await asyncio.gather(*tasks)

        for day, link in results:
            yt_links_by_day[day] = link
    coach_logger.log_info("[+] YouTube links fetched.")
    return yt_links_by_day

# def fetch_youtube_links(deka_urls):
#     coach_logger.log_info("[+] Fetching YouTube links...")
#     start_time = time.time()
#     result = asyncio.run(fetch_youtube_links_async(deka_urls))
#     # print("--- %s seconds ---" % (time.time() - start_time))
#     coach_logger.log_info(f"[+] YouTube links fetched in {time.time() - start_time} seconds")
#     return result

# deka_urls = [
#     'https://dekacomp.us4.list-manage.com/track/click?u=723a26c4b593ffbf674f2f44b&id=5210948b2c&e=00cac42032',
#     'https://dekacomp.us4.list-manage.com/track/click?u=723a26c4b593ffbf674f2f44b&id=206b155eeb&e=00cac42032',
#     'https://dekacomp.us4.list-manage.com/track/click?u=723a26c4b593ffbf674f2f44b&id=fc801c93a0&e=00cac42032',
#     'https://dekacomp.us4.list-manage.com/track/click?u=723a26c4b593ffbf674f2f44b&id=4d6fb39f08&e=00cac42032',
#     'https://dekacomp.us4.list-manage.com/track/click?u=723a26c4b593ffbf674f2f44b&id=d3fe739235&e=00cac42032',
#     'https://dekacomp.us4.list-manage.com/track/click?u=723a26c4b593ffbf674f2f44b&id=e169b96847&e=00cac42032',
# ]

# result = fetch_youtube_links(deka_urls)
# pp(result)