import asyncio
import decimal
import logging
import os.path
import re
from datetime import datetime
from enum import Enum, auto

import coloredlogs
import python_socks
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from peewee import DatabaseError
from telethon import TelegramClient, events, Button, utils
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault

from api import get_recipient, cre_order_and_pay
from configer import LOG_LEVEL, API_ID, PROXY_IP, API_HASH, PROXY_PORT, BOT_TOKEN, KEFU_URL, MSG_ID_TO_KE_HU, \
    MSG_TO_KE_HU, CRON_MIN
from models.Base import db
from models.payment import Payment, save_or_up_payment
from models.user import get_user_by_uid, save_or_up_user
from pay.tokenpay import call_pay
from pay.yizhifu import take_yizhifu_order, notify_yizhifu
from util import generate_order_number, download_image

coloredlogs.install(level=LOG_LEVEL)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
log = logging.getLogger('bot')

proxy = (python_socks.ProxyType.HTTP, PROXY_IP, PROXY_PORT) if PROXY_IP is not None else None
bot = TelegramClient('bot', API_ID, API_HASH, proxy=proxy).start(bot_token=BOT_TOKEN)

conversation_state = {}

scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')


class State(Enum):
    WAIT_USER_NAME = auto()


@bot.on(events.NewMessage(incoming=True))
async def echo_all_bot(event):
    if event.is_private:
        text = event.text
        who_name = utils.get_display_name(event.chat)
        who = event.sender_id
        user = get_user_by_uid(who, who_name)
        state = conversation_state.get(who)
        if text.startswith('/start'):
            buttons_home_menu = [
                [Button.text('个人中心', resize=True), Button.text('开通会员', resize=True),
                 Button.text('联系客服', resize=True)],
                [Button.text('关闭菜单', resize=True), Button.text('我的订单', resize=True),
                 Button.text('💰余额充值', resize=True)],
            ]
            await event.respond('欢迎使用<b>Telegram Premium</b>会员24小时自动开通服务',
                                parse_mode='html',
                                buttons=buttons_home_menu,
                                link_preview=False)
        elif text == '💰余额充值':
            await event.respond('''请选择支付类型
定价:
🔥3个月 / <code>15 U</code>
🔥半年 / <code>25 U</code>
🔥一年 / <code>40 U</code>
            ''', buttons=get_pay_buttons_type(), parse_mode='html')
        elif text == '个人中心':

            await event.respond('💁账号uid: <code>%s</code>\n'
                                '😀账号名称: %s\n\n'
                                '💰余额: %s USD\n' % (user.uid, user.name, user.balance)
                                , parse_mode='html'
                                )
        elif text == '开通会员':
            # if user.balance < 15:
            #     await event.respond('余额不足,请点击菜单中 💰余额充值 进行充值')
            #     return
            # 获取用户的
            await event.respond('请输入要充值的用户名\n'
                                '用户名以@开头 如: @xxxx')
            conversation_state[who] = State.WAIT_USER_NAME
        elif text.startswith('/余额操作 '):
            text = text.replace('/余额操作 ', '')
            arr = text.split(' ')
            user = get_user_by_uid(int(arr[0]))
            if len(arr) == 1:
                # 查询用户的余额
                await event.respond(
                    '💁账号uid: <code>%s</code>\n'
                    '😀账号名称: %s\n\n'
                    '💰余额: %s USD\n'
                    % (
                        user.uid, user.name, user.balance)
                    , parse_mode='html'
                )
            elif len(arr) == 2:
                add_mount = decimal.Decimal(arr[1])
                temp = user.balance
                user.balance += add_mount
                save_or_up_user(user)
                await event.respond(f'余额充值成功\n'
                                    f'原余额: {temp}\n'
                                    f'现余额: {user.balance}')

        elif text == '我的订单':
            payments = Payment.select().where(Payment.uid == who).order_by(Payment.cre_date.desc()).limit(5)
            if len(payments) == 0:
                await event.respond('暂无订单')
                return
            else:
                temp = ''
                for p in payments:
                    temp = temp + '<b>名称</b>: %s\n' \
                                  '单号: <code>%s</code>\n' \
                                  '状态: %s\n' \
                                  '金额: %s USD\n' \
                                  '创建时间: %s\n' \
                                  '支付时间: %s\n\n' % (
                               p.tra_name, p.tra_id, p.status, p.actualamount, p.cre_date,
                               p.pay_time if p.status == '已支付' else '')

                temp = temp + '<b>提示: 只显示最新的5个订单</b>'
                await event.respond(temp, parse_mode='html')

        elif state == State.WAIT_USER_NAME or text.startswith('@'):
            if who in conversation_state:
                del conversation_state[who]
            if len(text) > 1:
                info = await get_recipient(text)
                if 'error' in info:
                    if 'already' in info['error']:
                        await event.respond('此用户已订阅 Telegram Premium,请在订阅到期后再充值')
                    else:
                        await event.respond('未找到此Telegram用户')
                else:
                    user_name = info['found']['name']
                    img_content = info['found']['photo']
                    # 使用正则表达式提取URL
                    matches = re.findall(r'src="(.*?)"', img_content)
                    image_url = matches[0]
                    if 'base64' not in image_url:
                        await download_image(image_url, f'temp/{text}.jpg')

                    buttons = [
                        [Button.inline('3个月/15U', f'ord_{text}_3'), Button.inline('半年/25U', f'ord_{text}_6'), ],
                        [Button.inline('一年/40U', f'ord_{text}_12'), ],
                        [Button.inline('关闭', f'close_msg'), Button.url('联系客服', KEFU_URL)]
                    ]

                    await event.respond('开通用户: %s\n'
                                        '用户昵称: %s\n\n'
                                        '确认为此用户开通 Telegram Premium 会员吗？'
                                        % (text, user_name),
                                        file=f'temp/{text}.jpg' if os.path.exists(f'temp/{text}.jpg') else None,
                                        buttons=buttons
                                        )

            else:
                await event.respond('未找到此Telegram用户')

        elif text == '联系客服':
            await event.reply("联系客服: " + KEFU_URL)

            await cron_send_msg()

        elif text == '关闭菜单':
            await event.reply("菜单已关闭 , /start 开启菜单", buttons=Button.clear())


def get_pay_buttons_type():
    types = [
        [
            Button.inline('加密货币(cryptocurrency)', 'pay_bu_type_1'),
        ],
        # [
        #     Button.inline('🇨🇳支付宝', 'pay_type_yizhifu_alipay'),
        # ],
    ]

    return types


def get_pay_buttons(num):
    if num == 1:
        return [
            [Button.inline('USDT(TRC20)', 'pay_type_USDT_TRC20'), ],
            [Button.inline('TRX(TRC20)', 'pay_type_TRX')],
        ]


@events.register(events.CallbackQuery)
async def BotCallbackHandler(event):
    d = str(event.data, encoding="utf-8")
    who = event.sender_id
    if d.startswith('pay_bu_type_'):
        pay_type_num = int(d.replace('pay_bu_type_', ''))
        buttons = get_pay_buttons(pay_type_num)
        buttons.append([Button.inline('返回', 'bak_pay_menu')])
        await event.edit('请选择具体充值', buttons=buttons)

    elif d == 'bak_pay_menu':
        await event.edit('''请选择支付类型
定价:
🔥3个月 / <b>15 U</b>
🔥半年 / <b>25 U</b>
🔥一年 / <b>40 U</b>
                    ''', buttons=get_pay_buttons_type(), parse_mode='html')
    elif d.startswith('pay_type_'):
        pay_type = d.replace('pay_type_', '')
        await event.edit('请选择充值金额(USD)美元', buttons=[
            [
                Button.inline('15', f'pay_val_{pay_type}*15'),
            ],
            [
                Button.inline('25', f'pay_val_{pay_type}*25'),
            ],
            [
                Button.inline('40', f'pay_val_{pay_type}*40'),
            ],
            [
                Button.inline('返回', 'bak_pay_type')
            ]
        ])
    elif d.startswith('pay_val_'):
        pay_type, amount = d.replace('pay_val_', '').split('*')

        if pay_type.startswith('yizhifu_'):
            log.info('易支付')
            pay_type = pay_type.replace('yizhifu_', '')
            trid = generate_order_number(who)
            pay_to_amount = round(float(amount) * 7.22)
            pay_to_amount = "{:.2f}".format(pay_to_amount)
            json1, code = await take_yizhifu_order(trid, pay_to_amount, pay_type)
            if code == 200:
                qr_url = json1['qrcode']
                p = Payment()
                p.tra_id = trid
                p.uid = who
                p.tra_name = '支付宝充值'
                p.status = '未支付'
                p.actualamount = decimal.Decimal(amount)
                p.amount = decimal.Decimal(pay_to_amount)
                p.to_address = qr_url
                p.currency = pay_type
                save_or_up_payment(p)
                await event.edit(
                    '<b>支付类型</b>: %s \n' \
                    '<b>支付金额</b>: %s RMB\n' \
                    '<b>系统单号</b>: <code>%s</code>\n' % ('支付宝', p.amount, trid)
                    ,
                    parse_mode='html'
                    , buttons=[Button.url('点击支付', qr_url)]

                )
            else:
                log.info(json1)

        else:
            order_id = generate_order_number(who)
            json1, code = await call_pay(order_id, who, amount, currency=pay_type)
            info = json1['info']
            to_address = info['ToAddress']
            info_amount = info['Amount']
            expire_time = info['ExpireTime']

            p = Payment()
            p.tra_id = order_id
            p.uid = who
            p.actualamount = decimal.Decimal(amount)
            p.amount = decimal.Decimal(info_amount)
            p.to_address = to_address
            p.currency = pay_type
            p.tra_name = f'{pay_type} 充值订单'
            p.status = '未支付'
            save_or_up_payment(p)
            await event.edit('此订单30分钟内有效，过期后请重新生成订单。\n'
                             '➖➖➖➖➖➖➖➖➖➖\n'
                             '<b>您正在支付 %s 的 %s </b>\n'
                             '<b>转账地址</b>: <code>%s</code>\n'
                             '<b>转账金额</b>: <code>%s</code>\n'
                             '<b>过期时间</b>: %s\n'
                             '<b>单号</b>: <code>%s</code>\n'
                             '➖➖➖➖➖➖➖➖➖➖\n'
                             '请注意转账金额务必与<b>上方的转账金额一致</b>，否则无法自动到账支付完成后, 请等待5分钟左右查询，自动到账。' % (
                                 info['BlockChainName'], info['CurrencyName'], to_address, info_amount, expire_time,
                                 order_id)
                             , parse_mode='html', )
    elif d.startswith('ord_'):
        user_name, month = d.replace('ord_', '').split('_')
        # 创建订单即可
        p = Payment()
        order_id = generate_order_number(who)
        p.tra_id = order_id
        p.uid = who
        if month == '3':
            actualamount = 15
        elif month == '6':
            actualamount = 25
        else:
            actualamount = 40
        p.actualamount = decimal.Decimal(actualamount)
        p.tra_name = f'{user_name} {month}个月 Telegram Premium 会员'
        p.open_user = user_name
        p.currency = 'huiyuan'
        p.month = month
        p.status = '未支付'
        p = save_or_up_payment(p)
        await event.edit(
            '订单创建成功，请立即支付！\n'
            '订单号: <code>%s</code>\n'
            '商品名称: <b>%s</b>\n'
            '开通用户: %s\n'
            '下单时间: %s\n'
            '订单状态: %s\n'
            '订单金额: <b>%s USD</b>' % (p.tra_id, p.tra_name, p.open_user, p.cre_date, '未支付', p.actualamount),
            buttons=[
                [Button.inline('立即支付', f'pay_pre_{p.tra_id}'), Button.inline('取消订单', f'pay_del_{p.tra_id}'), ],
                [Button.inline('关闭', f'close_msg'), Button.url('联系客服', KEFU_URL)]
            ],
            parse_mode='html',
        )

    elif d.startswith('pay_pre_'):
        ord_id = d.replace('pay_pre_', '')
        p = Payment.get_or_none(Payment.tra_id == ord_id)
        user = get_user_by_uid(who)
        if user.balance - p.actualamount >= 0:
            user.balance = user.balance - p.actualamount
            p.status = '已支付'
            with db.atomic() as transaction:
                try:
                    save_or_up_payment(p)
                    save_or_up_user(user)
                    transaction.commit()
                except DatabaseError:
                    transaction.rollback()
            # 请求开通
            res_json = await get_recipient(p.open_user)
            recipient = res_json['found']['recipient']
            await event.edit('订单开通中,请在菜单中点击 我的订单 查看进度', buttons=None)

            await event.edit(
                '订单开通中,请在菜单中点击 我的订单 查看进度\n'
                '订单号: <code>%s</code>\n'
                '商品名称: <b>%s</b>\n'
                '开通用户: %s\n'
                '下单时间: %s\n'
                '订单状态: %s\n'
                '订单金额: <b>%s USD</b>' % (p.tra_id, p.tra_name, p.open_user, p.cre_date, '充值中', p.actualamount),
                buttons=[
                    [Button.inline('关闭', f'close_msg'), Button.url('联系客服', KEFU_URL)]
                ],
                parse_mode='html',
            )

            await cre_order_and_pay(recipient, p.tra_id, event, months=p.month)
        else:
            await event.respond('余额不足,请点击菜单中 💰余额充值 进行充值')
    elif d.startswith('pay_del_'):
        ord_id = d.replace('pay_del_', '')
        Payment.delete().where(Payment.tra_id == ord_id).execute()
        await event.delete()

    elif d == 'close_msg':
        await event.delete()


async def notify(request):
    """
    支付成功的回调
    :param request:
    :return:
    """

    data = await request.json()
    log.info('回调开始===========================')
    log.info(f'异步支付回调内容 {data}')
    pay_signature = data['Signature']
    del data['Signature']
    if True:
        # 验证签名成功
        log.info(f'充值成功回调:{data}')
        out_orderid = data['OutOrderId']
        payment = Payment.get_or_none(Payment.tra_id == out_orderid)
        payment.pay_time = datetime.strptime(data['PayTime'], "%Y-%m-%d %H:%M:%S")
        payment.actualamount = decimal.Decimal(data['ActualAmount'])
        payment.currency = data['Currency']
        payment.amount = decimal.Decimal(data['Amount'])
        payment.from_address = data['FromAddress']
        payment.taoken_pay_tra_id = data['Id']
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

        await bot.send_message(payment.uid, '''充值订单支付成功
系统单号: <code>%s</code>
充值单号: <code>%s</code>
+金额: <code>%s</code> USD
充值类型: <code>%s</code>
币种金额: <code>%s</code>
入账地址: <code>%s</code>
出账地址: <code>%s</code>
创建时间: <code>%s</code>
支付时间: <code>%s</code>'''

                               % (
                                   payment.tra_id, payment.taoken_pay_tra_id, payment.actualamount, payment.currency,
                                   payment.actualamount, payment.to_address, payment.from_address, payment.cre_date,
                                   payment.pay_time)
                               , parse_mode='HTML'
                               )

        return web.Response(text='ok')


async def wrapped_notify_yizhifu(request):
    return await notify_yizhifu(request, bot)


app = web.Application()

app.router.add_post('/notify_token_order', notify)
app.router.add_get('/notify_yizhifu', wrapped_notify_yizhifu)


async def cron_send_msg():
    bot_me = await bot.get_me()
    await bot.send_message(
        int(MSG_ID_TO_KE_HU),
        MSG_TO_KE_HU,
        file='./bg.jpg',
        buttons=[
            Button.url('立即开通尊贵的Premium会员', f'http://t.me/{bot_me.username}')
        ]
        , parse_mode='HTML'

    )


async def main():
    bot.add_event_handler(BotCallbackHandler)
    bot_me = await bot.get_me()
    commands = [
        BotCommand(command="start", description='开始使用'),

    ]
    await bot(
        SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='',
            commands=commands
        )
    )

    scheduler.add_job(cron_send_msg,
                      'interval',
                      minutes=CRON_MIN,
                      )
    scheduler.start()

    log.info(f'{bot_me.username} bot启动成功...')


bot.start()
loop = asyncio.get_event_loop()

try:
    loop.create_task(main())
    web.run_app(app, port=2334, loop=loop)
    loop.run_forever()
except KeyboardInterrupt:
    pass
