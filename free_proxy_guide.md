# Free Proxy Solutions Guide

This guide provides information on how to obtain and use free proxies with the property scraper.

## Free Proxy Sources

### 1. Public Proxy Lists

These websites provide regularly updated lists of free proxies:

- [Free Proxy List](https://free-proxy-list.net/)
- [Proxy Nova](https://www.proxynova.com/proxy-server-list/)
- [Proxy Scrape](https://proxyscrape.com/free-proxy-list)
- [Geonode Free Proxy List](https://geonode.com/free-proxy-list/)

You can manually copy proxies from these sites and add them to your `config.json` file.

### 2. Proxy Rotation Libraries

Python libraries that can help with finding and rotating free proxies:

```bash
pip install free-proxy
pip install proxy-randomizer
```

Example usage with free-proxy:

```python
from fp.fp import FreeProxy

proxy = FreeProxy(country_id=['US', 'BR'], timeout=1).get()
```

### 3. Tor Network

The Tor network can be used as a free proxy solution:

1. Install Tor Browser: https://www.torproject.org/download/
2. Install the Python library to connect to Tor:

   ```bash
   pip install stem
   pip install PySocks
   ```

3. Configure Selenium to use Tor as a proxy:

   ```python
   from selenium import webdriver
   from selenium.webdriver.chrome.options import Options

   chrome_options = Options()
   chrome_options.add_argument('--proxy-server=socks5://127.0.0.1:9050')
   driver = webdriver.Chrome(options=chrome_options)
   ```

### 4. Free VPN Services

Some VPN services offer free tiers with limited data:

- ProtonVPN (Free tier)
- Windscribe (10GB/month free)
- Hide.me (2GB/month free)

## Implementing Free Proxy Rotation

### Method 1: Scrape and Use Free Proxies

Add this code to your project to automatically scrape and test free proxies:

```python
import requests
from bs4 import BeautifulSoup
import random
import concurrent.futures

def get_free_proxies():
    """Scrape free proxies from free-proxy-list.net"""
    url = 'https://free-proxy-list.net/'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    proxies = []
    proxy_table = soup.find('table', {'id': 'proxylisttable'})

    # Skip header row
    for row in proxy_table.tbody.find_all('tr'):
        cells = row.find_all('td')
        ip = cells[0].text
        port = cells[1].text
        https = cells[6].text

        if https == 'yes':
            proxy = f'https://{ip}:{port}'
            proxies.append(proxy)
        else:
            proxy = f'http://{ip}:{port}'
            proxies.append(proxy)

    return proxies

def is_proxy_working(proxy, test_url='http://www.google.com', timeout=5):
    """Test if a proxy is working"""
    try:
        response = requests.get(
            test_url,
            proxies={'http': proxy, 'https': proxy},
            timeout=timeout
        )
        return response.status_code == 200
    except:
        return False

def get_working_proxies(max_workers=10, min_proxies=5):
    """Get a list of working proxies"""
    all_proxies = get_free_proxies()
    working_proxies = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_proxy = {executor.submit(is_proxy_working, proxy): proxy for proxy in all_proxies}

        for future in concurrent.futures.as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            try:
                if future.result():
                    working_proxies.append(proxy)
                    print(f"Found working proxy: {proxy}")

                    # If we have enough proxies, break early
                    if len(working_proxies) >= min_proxies:
                        break
            except Exception as e:
                print(f"Error testing proxy {proxy}: {e}")

    return working_proxies
```

### Method 2: Use Proxy Rotation Services with Free Tiers

Some proxy rotation services offer free tiers:

- Scraper API (1,000 free requests)
- ScrapingBee (limited free plan)
- ZenRows (free tier available)

## Cautions When Using Free Proxies

1. **Reliability**: Free proxies are often unreliable and may stop working
2. **Speed**: Free proxies are typically slower than paid ones
3. **Security**: Free proxies may monitor your traffic
4. **IP Blocking**: Free proxies are often already blocked by many websites
5. **Limited Availability**: The number of working free proxies is limited

## Best Practices

1. Always test proxies before using them
2. Implement proper error handling for proxy failures
3. Rotate proxies frequently
4. Use a longer delay between requests when using free proxies
5. Consider using a combination of methods (Tor + free proxies)
