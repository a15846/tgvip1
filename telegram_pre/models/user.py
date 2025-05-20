from peewee import BigIntegerField, CharField, DecimalField

from models.Base import BaseModel


class User(BaseModel):
    uid = BigIntegerField(primary_key=True, help_text='用户id', )
    name = CharField(default='', help_text='用户名')
    balance = DecimalField(max_digits=8, decimal_places=2, default=0.00,
                           help_text='价格 单位usd')
    language = CharField(default='zh_CN')



User.create_table()


def save_or_up_user(user: User):
    try:
        updated = user.save()
        if not updated:
            user.save(force_insert=True)
        return user
    except Exception as e:
        print(e.args[0])
    return user


def get_user_by_uid(who: int, who_name=''):
    user = User.get_or_none(User.uid == who)
    if user is None:
        user = User()
        user.uid = who
        if who_name:
            user.name = who_name
        save_or_up_user(user)
    return user
