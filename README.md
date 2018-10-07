# TumblrCollector
----

## Desc
this is tumblr collector tools, improve tumblr-crawler.

## Setup
```bash
$ git clone https://github.com/webignorant/tumblr_collector.git TumblrCollector
$ cd TumblrCollector
$ pip install -r requirements.txt
```

## Config

#### conf_sites.txt
> Set up the collected site
> tumblr site name, one per line!

#### conf.json
> custom collector conf
```
{
    // threads num
    "THREADS": 10,
    "REQUEST": {
        "TIMEOUT": 10,
        "RETRY": 5,
        "OFFSET": 0,
        "LIMIT": 50,
        "IS_DOWNLOAD_IMG": true,
        "IS_DOWNLOAD_VIDEO": true,
        "IS_DOWNLOAD_TEXT": true
    },
    "LOG": {
        "FORCE_POSTS_LOG": false
    }
}

```

#### conf_proxies.json
> use requests proxy
```
{
    "http": "127.0.0.1:8787",
    "https": "127.0.0.1:8787",
    "http": "socks5://user:pass@host:port",
    "https": "socks5://127.0.0.1:1080"
}
```

## Run
```bash
python tumblr-collector.py
```
