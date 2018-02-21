import asyncio
import time
from collections import OrderedDict, namedtuple
from ledger.util import F
from plenum.common.constants import MSG_TYPE

Reply = namedtuple("REPLY", ['result'])

fields = OrderedDict([
    ("identifier", (str, str)),
    ("reqId", (str, int)),
    ("txnId", (str, str)),
    ("txnTime", (str, float)),
    ("txnType", (str, str)),
])


def testTxnPersistence(ledger):
    loop = asyncio.get_event_loop()

    def go():
        identifier = "testClientId"
        reply = Reply(result={
            "identifier": identifier,
            "reqId": 1,
            MSG_TYPE: "buy"
        })
        sizeBeforeInsert = ledger.size
        ledger.append(reply.result)
        txn_in_db = ledger.get(identifier=identifier,
                               reqId=reply.result['reqId'])
        txn_in_db.pop(F.seqNo.name)
        assert txn_in_db == reply.result
        assert ledger.size == sizeBeforeInsert + 1
        ledger.reset()
        ledger.stop()

    go()
    loop.close()
