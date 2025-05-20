import hashlib

import aiohttp
from aiohttp import TCPConnector

from configer import PAY_API_KEY, NOTIFY_URL, PAY_API_URL
from util import process_response


# 获取待签名字符串
def sign(dic, key=PAY_API_KEY):
    dics = dict(sorted(dic.items()))
    lt = []
    for k, v in dics.items():
        lt.append(k + '=' + str(v))
    return '&'.join(lt) + key


# 签名
def get_signature(sign):
    md = hashlib.md5()
    # 对stringA字符串进行编码
    md.update(sign.encode('utf-8'))
    # 数据加密
    signValue = md.hexdigest()
    # 转为小写
    return signValue.lower()


async def call_pay(order_id, uid, actual_amount, currency='USDT_TRC20'):
    data = {
        'OutOrderId': order_id,
        'OrderUserKey': str(uid),
        'ActualAmount': actual_amount,  # 订单实际支付的金额
        'Currency': currency,
        'NotifyUrl': f'{NOTIFY_URL}/notify_token_order',
    }
    sig = sign(data)
    signature = get_signature(sig)
    data['Signature'] = signature

    async with aiohttp.ClientSession(connector=TCPConnector(verify_ssl=False)) as session:
        async with session.post(f'{PAY_API_URL}/CreateOrder', json=data,
                                headers={'Content-Type': 'application/json'}) as resp:
            return await process_response(resp)
