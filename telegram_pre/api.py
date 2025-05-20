import asyncio
import base64
import logging
from pprint import pprint
from sqlite3 import DatabaseError

import aiohttp
from ton.sync import TonlibClient
from ton.tonlibjson import TonlibError

from configer import WALLET_KEY, COOKIE, HASH, ADMIN_ID
from models.Base import db
from models.payment import Payment, save_or_up_payment
from models.user import save_or_up_user, get_user_by_uid

req_url = f'https://fragment.com/api?hash={HASH}'

cookies = {}
for line in COOKIE.split(";"):
    if line.find("=") != -1:
        name, value = line.strip().split("=")
        cookies[name] = value


async def get_recipient(user_name, months=3):
    url = f'{req_url}&query={user_name}&months={months}&method=searchPremiumGiftRecipient'
    async with aiohttp.ClientSession(cookies=cookies) as session:
        async with session.post(url) as response:
            print(await response.text())
            res_json = await response.json()
            # res_json['found']['recipient']
            return res_json


async def make_request(session, url):
    print(url)
    async with session.post(url, cookies=cookies) as response:
        return await response.json()


async def cre_order_and_pay(recipient, ord_id, event, months=3):
    init_gift_url = f'{req_url}&recipient={recipient}&months={months}&method=initGiftPremiumRequest'
    async with aiohttp.ClientSession() as session:
        res_json = await make_request(session, init_gift_url)
        print(res_json)
        req_id = res_json['req_id']

        # Confirm order
        confirm_url = f'{req_url}&id={req_id}&show_sender=1&method=getGiftPremiumLink'
        res_json = await make_request(session, confirm_url)
        id = res_json['check_params']['id']

        # Get payment information
        pay_info_url = f'https://fragment.com/tonkeeper/rawRequest?id={id}&qr=1'
        res_json = await make_request(session, pay_info_url)
        messages_ = res_json['body']['params']['messages'][0]
        address = messages_['address']
        amount = messages_['amount']
        payload = messages_['payload']

        payload += "=" * ((4 - len(payload) % 4) % 4)
        decoded_bytes = base64.b64decode(payload)

        payload = decoded_bytes[-8:].decode('utf-8')
        p = Payment.get_or_none(Payment.tra_id == ord_id)
        p.taoken_pay_tra_id = payload
        save_or_up_user(p)

        logging.info(payload)
        client = TonlibClient()
        TonlibClient.enable_unaudited_binaries()
        await client.init_tonlib()
        wallet = await client.import_wallet(
            word_list=WALLET_KEY)
        print('钱包地址:', wallet.address)
        try:
            result = await wallet.transfer('EQBAjaOyi2wGWlk-EDkSabqqnF-MrrwMadnwqrurKpkla9nE', amount,
                                           comment=f'Telegram Premium for {p.month} months Ref#{payload}')
            p = Payment.get_or_none(Payment.tra_id == ord_id)
            p.status = '开通成功'
            save_or_up_user(p)
            logging.info(result)

            # 通知管理
            await event.client.send_message(int(ADMIN_ID), '会员订单开通成功！！！,\n'
                                                           '订单号: <code>%s</code>\n'
                                                           '商品名称: <b>%s</b>\n'
                                                           '开通用户: %s\n'
                                                           '下单时间: %s\n'
                                                           '订单状态: %s\n'
                                                           '订单金额: <b>%s USD</b>'
                                                           '三方订单号: %s' % (
                                                p.tra_id, p.tra_name, p.open_user, p.cre_date, '开通成功',
                                                p.actualamount,
                                                p.taoken_pay_tra_id), )


        except TonlibError as e:
            if str(e) == 'NOT_ENOUGH_FUNDS':
                logging.warning('代理支付钱包余额不足,请联系客服')
                await event.respond('代理支付钱包余额不足,请联系客服')
            else:
                await event.respond(str(e))
            p = Payment.get_or_none(Payment.tra_id == ord_id)
            p.err_msg = str(e)
            p.status='开通失败，余额退还'
            user = get_user_by_uid(p.uid)
            with db.atomic() as transaction:
                try:
                    # 为用户增加余额
                    user.balance = user.balance + p.actualamount
                    save_or_up_payment(p)
                    save_or_up_user(user)
                    transaction.commit()
                except DatabaseError:
                    transaction.rollback()
            save_or_up_user(p)
        return messages_


async def main():
    res_json = await get_recipient('@nnznnsn')
    pprint(res_json)


if __name__ == '__main__':
    # recipient = get_user_info('jjmmmmjj')
    # req_id = cre_order(recipient)
    # print(req_id)
    # get_order_status('EH2Uu7WpBO3Ogh6iFEkQjSkW')
    asyncio.get_event_loop().run_until_complete(main())
