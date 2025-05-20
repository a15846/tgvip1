import yaml

with open('./db/config.yml', 'r', encoding='utf-8') as f:
    result = yaml.load(f.read(), Loader=yaml.FullLoader)

API_ID = result['API_ID']
API_HASH = result['API_HASH']
BOT_TOKEN = result['BOT_TOKEN']
PROXY_IP = result['PROXY_IP']
PROXY_PORT = result['PROXY_PORT']
ADMIN_ID = result['ADMIN_ID']
LOG_LEVEL = result['LOG_LEVEL']
DATA_BASE = result['DATA_BASE']
IP = result['IP']
PORT = result['PORT']
USER = result['USER']
PASSWD = result['PASSWD']
PAY_API_URL = result['PAY_API_URL']
PAY_API_KEY = result['PAY_API_KEY']
NOTIFY_URL = result['NOTIFY_URL']
WALLET_KEY = result['WALLET_KEY']
KEFU_URL = result['KEFU_URL']
MSG_ID_TO_KE_HU = result['MSG_ID_TO_KE_HU']
MSG_TO_KE_HU = result['MSG_TO_KE_HU']
CRON_MIN = result['CRON_MIN']
COOKIE = result['COOKIE']
HASH = result['HASH']