#
# Copyright 2013 The py-lmdb authors, all rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted only as authorized by the OpenLDAP
# Public License.
#
# A copy of this license is available in the file LICENSE in the
# top-level directory of the distribution or, alternatively, at
# <http://www.OpenLDAP.org/license.html>.
#
# OpenLDAP is a registered trademark of the OpenLDAP Foundation.
#
# Individual files and/or contributed packages may be copyright by
# other parties and/or subject to additional restrictions.
#
# This work also contains materials derived from public sources.
#
# Additional information about OpenLDAP can be obtained at
# <http://www.openldap.org/>.
#

# This is not a test suite! More like a collection of triggers for previously
# observed crashes. Want to contribute to py-lmdb? Please write a test suite!
#
# what happens when empty keys/ values passed to various funcs
# incorrect types
# try to break cpython arg parsing - too many/few/incorrect args
# Various efforts to cause Python-level leaks.
#

from __future__ import absolute_import
from __future__ import with_statement

import os
import random
import unittest

import lmdb
import testlib

from testlib import B
from testlib import O


try:
    next(iter([1]))
except NameError: # Python2.5.
    def next(it):
        return it.next()


class CrashTest(unittest.TestCase):
    # Various efforts to cause segfaults.

    def setUp(self):
        self.path, self.env = testlib.temp_env()
        with self.env.begin(write=True) as txn:
            txn.put(B('dave'), B(''))
            txn.put(B('dave2'), B(''))

    def testOldCrash(self):
        txn = self.env.begin()
        dir(iter(txn.cursor()))

    def testCloseWithTxn(self):
        txn = self.env.begin(write=True)
        self.env.close()
        self.assertRaises(Exception, (lambda: list(txn.cursor())))

    def testDoubleClose(self):
        self.env.close()
        self.env.close()

    def testDbDoubleClose(self):
        db = self.env.open_db(name='dave3')
        #db.close()
        #db.close()

    def testTxnCloseActiveIter(self):
        with self.env.begin() as txn:
            it = txn.cursor().iternext()
        self.assertRaises(Exception, (lambda: list(it)))

    def testDbCloseActiveIter(self):
        db = self.env.open_db(name='dave3')
        with self.env.begin(write=True) as txn:
            txn.put(B('a'), B('b'), db=db)
            it = txn.cursor(db=db).iternext()
        self.assertRaises(Exception, (lambda: list(it)))


class IteratorTest(unittest.TestCase):
    def setUp(self):
        self.path, self.env = testlib.temp_env()
        self.txn = self.env.begin(write=True)
        self.c = self.txn.cursor()

    def testEmpty(self):
        self.assertEqual([], list(self.c))
        self.assertEqual([], list(self.c.iternext()))
        self.assertEqual([], list(self.c.iterprev()))

    def testFilled(self):
        testlib.putData(self.txn)
        self.assertEqual(testlib.ITEMS, list(self.c))
        self.assertEqual(testlib.ITEMS, list(self.c))
        self.assertEqual(testlib.ITEMS, list(self.c.iternext()))
        self.assertEqual(testlib.ITEMS[::-1], list(self.txn.cursor().iterprev()))
        self.assertEqual(testlib.ITEMS[::-1], list(self.c.iterprev()))
        self.assertEqual(testlib.ITEMS, list(self.c))

    def testFilledSkipForward(self):
        testlib.putData(self.txn)
        self.c.set_range(B('b'))
        self.assertEqual(testlib.ITEMS[1:], list(self.c))

    def testFilledSkipReverse(self):
        testlib.putData(self.txn)
        self.c.set_range(B('b'))
        self.assertEqual(testlib.REV_ITEMS[-2:], list(self.c.iterprev()))

    def testFilledSkipEof(self):
        testlib.putData(self.txn)
        self.assertEqual(False, self.c.set_range(B('z')))
        self.assertEqual(testlib.REV_ITEMS, list(self.c.iterprev()))


class BigReverseTest(unittest.TestCase):
    # Test for issue with MDB_LAST+MDB_PREV skipping chunks of database.
    def test_big_reverse(self):
        path, env = testlib.temp_env()
        txn = env.begin(write=True)
        keys = [B('%05d' % i) for i in range(0xffff)]
        for k in keys:
            txn.put(k, k, append=True)
        assert list(txn.cursor().iterprev(values=False)) == list(reversed(keys))


class MultiCursorDeleteTest(unittest.TestCase):
    def setUp(self):
        self.path, self.env = testlib.temp_env()

    def test1(self):
        """Ensure MDB_NEXT is ignored on `c1' when it was previously positioned
        on the key that `c2' just deleted."""
        txn = self.env.begin(write=True)
        cur = txn.cursor()
        while cur.first():
            cur.delete()

        for i in range(1, 10):
            cur.put(O(ord('a') + i) * i, B(''))

        c1 = txn.cursor()
        c1f = c1.iternext(values=False)
        while next(c1f) != B('ddd'):
            pass
        c2 = txn.cursor()
        assert c2.set_key(B('ddd'))
        c2.delete()
        assert next(c1f) == B('eeee')

    def test_monster(self):
        # Generate predictable sequence of sizes.
        rand = random.Random()
        rand.seed(0)

        txn = self.env.begin(write=True)
        keys = []
        for i in range(20000):
            key = B('%06x' % i)
            val = B('x' * rand.randint(76, 350))
            assert txn.put(key, val)
            keys.append(key)

        deleted = 0
        for key in txn.cursor().iternext(values=False):
            assert txn.delete(key), key
            deleted += 1

        assert deleted == len(keys), deleted


if __name__ == '__main__':
    unittest.main()
