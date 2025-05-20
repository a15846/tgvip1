from peewee import MySQLDatabase, OperationalError, __exception_wrapper__, Model

from configer import DATA_BASE, IP, PORT, USER, PASSWD


class RetryOperationalError(object):
    def execute_sql(self, sql, params=None, commit=True):
        try:
            cursor = super(RetryOperationalError, self).execute_sql(
                sql, params, commit)
        except OperationalError:
            if not self.is_closed():
                if self.in_transaction():
                    is_open = not self._state.closed
                    try:
                        if is_open:
                            with __exception_wrapper__:
                                self._close(self._state.conn)
                    finally:
                        self._state.closed = True
                        self._state.conn = None
                    raise OperationalError('request in transaction while mysql has gone away')
                else:
                    self.close()
            with __exception_wrapper__:
                cursor = self.cursor()
                cursor.execute(sql, params or ())
                if commit and not self.in_transaction():
                    self.commit()
        return cursor


class RetryMySQLDatabase(RetryOperationalError, MySQLDatabase):
    pass


# db = MySQLDatabase(
#
#     DATA_BASE, host=IP, port=PORT, user=USER, passwd=PASSWD
# )

# db = SqliteDatabase('./db/date.db')


Links = {
    "host": IP,
    "port": PORT,
    "user": USER,
    "passwd": PASSWD,
    "database": DATA_BASE
}

db = RetryMySQLDatabase(**Links)




class BaseModel(Model):
    class Meta:
        database = db
