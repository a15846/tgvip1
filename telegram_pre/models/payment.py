from datetime import datetime

from peewee import CharField, DecimalField, DateTimeField, BigIntegerField, TextField

from models.Base import BaseModel


# 订单记录，包括购买记录
class Payment(BaseModel):
    tra_id = CharField(primary_key=True, help_text='交易记录id')
    uid = BigIntegerField(help_text='用户id')
    tra_name = CharField(default='', help_text='订单名称')
    month = CharField(default='', help_text='开通几月')
    open_user = CharField(default='', help_text='开通用户')

    # 创建时间
    cre_date = DateTimeField(default=datetime.now, formats='%Y-%m-%d %H:%M:%S')

    actualamount = DecimalField(max_digits=8, decimal_places=2, default=0.00,
                                help_text='本地货币的金额 单位 USD')

    # 币种  Enum, 支持USDT_TRC20、TRX等
    currency = CharField()

    # 订单金额，此金额为设置 币种 转换为 Currency字段指定的币种后的金额
    amount = DecimalField(max_digits=8, decimal_places=2, default=0.00,
                          help_text='币种金额')
    # 付款地址
    from_address = CharField(default='')

    # 付款状态  未支付 已支付  已超时
    status = CharField(default=0)

    # 收款地址
    to_address = CharField(default='')

    # 支付时间
    pay_time = DateTimeField(default=datetime.now, formats='%Y-%m-%d %H:%M:%S')

    # 支付商的单号，方便排查问题
    taoken_pay_tra_id = CharField(default='')

    err_msg = TextField(default='')


Payment.create_table()


def save_or_up_payment(payment: Payment):
    try:
        updated = payment.save()
        if not updated:
            payment.save(force_insert=True)
        return payment
    except Exception as e:
        print(e.args[0])
    return payment
