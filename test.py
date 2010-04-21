# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import time
import unittest

import contrib
import mox
import stubout
from tornado import ioloop
from twisted.internet import defer
from twisted.python import failure

import fakerabbit
import flags


FLAGS = flags.FLAGS


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        super(BaseTestCase, self).setUp()

        # emulate some of the mox stuff, we can't use the metaclass
        # because it screws with our generators
        self.mox = mox.Mox()
        self.stubs = stubout.StubOutForTesting()
        
        # TODO(termie): we could possibly keep a more global registry of
        #               the injected listeners... this is fine for now though
        self.injected = []
        self.ioloop = ioloop.IOLoop.instance()
  
        self._waiting = None
        self._doneWaiting = False
        self._timedOut = False

    def tearDown(self):
        super(BaseTestCase, self).tearDown()
        self.mox.UnsetStubs()
        self.stubs.UnsetAll()
        self.stubs.SmartUnsetAll()
        self.mox.VerifyAll()

        for x in self.injected:
            x.stop()

        if FLAGS.fake_rabbit:
            fakerabbit.reset_all()

    def _waitForTest(self, timeout=60):
        """ Push the ioloop along to wait for our test to complete. """
        self._waiting = self.ioloop.add_timeout(time.time() + timeout,
                                                self._timeout)
        def _wait():
            if self._timedOut:
                self.fail('test timed out')
                self._done()
            if self._doneWaiting:
                self.ioloop.stop()
                return
            # we can use add_callback here but this uses less cpu when testing
            self.ioloop.add_timeout(time.time() + 0.01, _wait)

        self.ioloop.add_callback(_wait)
        self.ioloop.start()

    def _done(self):
        if self._waiting:
            try:
                self.ioloop.remove_timeout(self._waiting)
            except Exception:
                pass
            self._waiting = None
        self._doneWaiting = True
    
    def _maybeInlineCallbacks(self, f):
        """ If we're doing async calls in our tests, wait on them.
        
        This is probably the most complicated hunk of code we have so far.

        First up, if the function is normal (not async) we just act normal
        and return.

        Async tests will use the "Inline Callbacks" pattern, which means
        you yield Deferreds at every "waiting" step of your code instead
        of making epic callback chains.

        Example (callback chain, ugly):
    
        d = self.node.terminate_instance(instance_id) # a Deferred instance
        def _describe(_):
            d_desc = self.node.describe_instances() # another Deferred instance
            return d_desc
        def _checkDescribe(rv):
            self.assertEqual(rv, [])
        d.addCallback(_describe)
        d.addCallback(_checkDescribe)
        d.addCallback(lambda x: self._done())
        self._waitForTest()
        
        Example (inline callbacks! yay!):

        yield self.node.terminate_instance(instance_id)
        rv = yield self.node.describe_instances()
        self.assertEqual(rv, [])

        If the test fits the Inline Callbacks pattern we will automatically
        handle calling wait and done.
        """
        # TODO(termie): this can be a wrapper function instead and
        #               and we can make a metaclass so that we don't
        #               have to copy all that "run" code below.
        g = f()
        if not hasattr(g, 'send'):
            self._done()
            return defer.succeed(g)
        
        inlined = defer.inlineCallbacks(f)
        d = inlined()
        return d
    
    def _catchExceptions(self, result, failure):
        exc = (failure.type, failure.value, failure.getTracebackObject())
        if isinstance(failure.value, self.failureException):
            result.addFailure(self, exc)
        elif isinstance(failure.value, KeyboardInterrupt):
            raise
        else:
            result.addError(self, exc)

        self._done()

    def _timeout(self):
        self._waiting = False
        self._timedOut = True

    def run(self, result=None):
        if result is None: result = self.defaultTestResult()

        result.startTest(self)
        testMethod = getattr(self, self._testMethodName)
        try:
            try:
                self.setUp()
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, self._exc_info())
                return

            ok = False
            try:
                d = self._maybeInlineCallbacks(testMethod)
                d.addErrback(lambda x: self._catchExceptions(result, x))
                d.addBoth(lambda x: self._done() and x)
                self._waitForTest()
                ok = True
            except self.failureException:
                result.addFailure(self, self._exc_info())
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, self._exc_info())

            try:
                self.tearDown()
            except KeyboardInterrupt:
                raise
            except:
                result.addError(self, self._exc_info())
                ok = False
            if ok: result.addSuccess(self)
        finally:
            result.stopTest(self)
