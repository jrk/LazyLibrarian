from __future__ import with_statement

import os
import sqlite3
import threading
import time

import lazylibrarian

from lazylibrarian import logger

db_lock = threading.Lock()


def dbFilename(filename="lazylibrarian.db"):

    return os.path.join(lazylibrarian.DATADIR, filename)


class DBConnection:

    def __init__(self, filename="lazylibrarian.db"):
        self.filename = filename
        self.connection = sqlite3.connect(dbFilename(filename), 20)
        self.connection.row_factory = sqlite3.Row

    def action(self, query, args=None):
        with db_lock:

            if not query:
                return

            sqlResult = None
            attempt = 0

            while attempt < 5:

                try:
                    if not args:
                        # logger.debug(self.filename+": "+query)
                        sqlResult = self.connection.execute(query)
                    else:
                        # logger.debug(self.filename+": "+query+" with args "+str(args))
                        sqlResult = self.connection.execute(query, args)
                    self.connection.commit()
                    break

                except sqlite3.OperationalError as e:
                    if "unable to open database file" in e.message or "database is locked" in e.message:
                        logger.warn('Database Error: %s' % e)
                        attempt += 1
                        time.sleep(1)
                    else:
                        logger.error('Database error: %s' % e)
                        raise

                except sqlite3.DatabaseError as e:
                    logger.error('Fatal error executing %s :: %s' % (query, e))
                    raise

            return sqlResult

    def match(self, query, args=None):
        try:
            # if there are no results, action() returns None and .fetchone() fails
            sqlResults = self.action(query, args).fetchone()
        except Exception:
            sqlResults = None
        if not sqlResults:
            return []

        return sqlResults

    def select(self, query, args=None):
        try:
            # if there are no results, action() returns None and .fetchall() fails
            sqlResults = self.action(query, args).fetchall()
        except Exception:
            sqlResults = None
        if not sqlResults:
            return []

        return sqlResults

    def genParams(self, myDict):
        return [x + " = ?" for x in myDict.keys()]

    def upsert(self, tableName, valueDict, keyDict):
        changesBefore = self.connection.total_changes

        # genParams = lambda myDict: [x + " = ?" for x in myDict.keys()]

        query = "UPDATE " + tableName + " SET " + ", ".join(self.genParams(valueDict)) + \
            " WHERE " + " AND ".join(self.genParams(keyDict))

        self.action(query, valueDict.values() + keyDict.values())

        if self.connection.total_changes == changesBefore:
            query = "INSERT INTO " + tableName + " (" + ", ".join(valueDict.keys() + keyDict.keys()) + ")" + \
                " VALUES (" + ", ".join(["?"] * len(valueDict.keys() + keyDict.keys())) + ")"
            self.action(query, valueDict.values() + keyDict.values())
