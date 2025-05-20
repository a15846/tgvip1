import time

import aiohttp
from aiohttp import TCPConnector

from configer import PROXY_IP, PROXY_PORT


async def process_response(response):
    content_type = response.headers.get('content-type', '')
    if 'json' in content_type:
        error_msg = await response.json()
    elif 'octet-stream' in content_type:
        return response
    else:
        error_msg = response.text

    if response.ok:
        return await response.json(), response.status
    else:
        print(f'调用接口 {response.url} 报错出错: {error_msg}')
        return error_msg, response.status


def generate_order_number(user_id):
    """
    订单号生成
    :param user_id: 用户ID
    :return: 订单号
    """
    timestamp = str(int(time.time()))
    return f'{time.strftime("%H%M%S", time.localtime())}{timestamp}{user_id}'


async def download_image(url, save_path):
    async with aiohttp.ClientSession(connector=TCPConnector(verify_ssl=False)) as session:
        if PROXY_IP:
            proxy_url = f"http://{PROXY_IP}:{PROXY_PORT}"
        else:
            proxy_url = None
        async with session.get(url, proxy=proxy_url) as response:
            if response.status == 200:
                with open(save_path, 'wb') as f:
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                print("图片下载成功：", save_path)
            else:
                print("无法下载图片。状态码:", response.status)
