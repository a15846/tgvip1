import asyncio
import hashlib
import logging
from datetime import datetime
from pprint import pprint

import aiohttp
from aiohttp import web
from peewee import DatabaseError

from configer import NOTIFY_URL
from models.Base import db
from models.payment import Payment, save_or_up_payment
from models.user import get_user_by_uid, save_or_up_user
from util import process_response

PAY_API_KEY = 'xKUUK9KnEN4zUCe8KUu8ErYCXN8YRvNu'
SHANG_HU_ID = 1013
log = logging.getLogger('yizhifu')


# MD5

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


async def take_yizhifu_order(order_id, amount, pay_type='wxpay'):
    url = 'https://payseals.com/mapi.php'

    data = {
        'pid': SHANG_HU_ID,  # 商户名称
        'type': pay_type,
        'out_trade_no': order_id,
        'notify_url': f"{NOTIFY_URL}/notify_yizhifu",
        'name': 'VIP会员',
        'money': amount,
        'clientip': '192.168.1.100',
    }
    sig = sign(data)
    signature = get_signature(sig)
    data['sign'] = signature
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            return await process_response(response)


async def notify_yizhifu(request, bot):
    data = dict(request.query.items())
    log.info('yizhifu回调开始===========================')
    log.info(f'异步支付回调内容 {data}')
    pay_signature = data['sign']
    del data['sign']
    if 'sign_type' in data:
        del data['sign_type']
    if 'param' in data and data['param'] == '':
        del data['param']
    sig = sign(data)
    signature = get_signature(sig)
    log.info(f'签名对比 {pay_signature} {signature}')
    if pay_signature == signature:
        out_trade_no = data['out_trade_no']
        # 外部订单号
        trade_no = data['trade_no']
        trade_status = data['trade_status']
        if trade_status == 'TRADE_SUCCESS':
            payment = Payment.get_or_none(Payment.tra_id == out_trade_no)
            payment.from_address = 'yizhifu'
            payment.taoken_pay_tra_id = trade_no
            payment.pay_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payment.status = '已支付'
            user = get_user_by_uid(payment.uid)
            with db.atomic() as transaction:
                try:
                    # 为用户增加余额
                    user.balance = user.balance + payment.actualamount
                    save_or_up_payment(payment)
                    save_or_up_user(user)
                    transaction.commit()
                except DatabaseError:
                    transaction.rollback()
            await bot.send_message(payment.uid,
                                   '充值订单支付成功\n' \
                                   '系统单号: <code>%s</code>\n' \
                                   '充值单号: <code>%s</code>\n' \
                                   '+金额: <code>%s</code> USD\n' \
                                   '充值类型: <code>%s</code>\n' \
                                   '币种金额: <code>%s</code>\n' \
                                   '入账地址: <code>%s</code>\n' \
                                   '出账地址: <code>%s</code>\n' \
                                   '创建时间: <code>%s</code>\n' \
                                   '支付时间: <code>%s</code>\n' % (
                                       payment.tra_id, payment.taoken_pay_tra_id, payment.actualamount,
                                       payment.currency,
                                       payment.actualamount, payment.to_address, payment.from_address, payment.cre_date,
                                       payment.pay_time)
                                   , parse_mode='HTML'
                                   )
            log.info('支付成功响应！！！')
            return web.Response(text='success')
