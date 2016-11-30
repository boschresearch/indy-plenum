import json
import os
from collections import OrderedDict
from typing import Any, Sequence, List, Dict

from ledger.stores.directory_store import DirectoryStore
from ledger.util import F
from plenum.common.has_file_storage import HasFileStorage
from plenum.common.txn_util import getTxnOrderedFields
from plenum.common.types import f
from plenum.common.request import Request
from plenum.common.util import updateFieldsWithSeqNo
from plenum.persistence.client_req_rep_store import ClientReqRepStore


class ClientReqRepStoreFile(ClientReqRepStore, HasFileStorage):
    def __init__(self, name, baseDir):
        self.baseDir = baseDir
        self.dataDir = "data/clients"
        self.name = name
        HasFileStorage.__init__(self, name=self.name, baseDir=baseDir,
                                dataDir=self.dataDir)
        if not os.path.exists(self.dataLocation):
            os.makedirs(self.dataLocation)
        self.reqStore = DirectoryStore(self.dataLocation, "Requests")
        self._serializer = None

    @property
    def lastReqId(self) -> int:
        reqIds = self.reqStore.keys
        return max(map(int, reqIds)) if reqIds else 0

    def addRequest(self, req: Request):
        idr = req.identifier
        reqId = req.reqId
        key = "{}{}".format(idr, reqId)
        self.reqStore.appendToValue(key, "0:{}".
                                    format(self.serializeReq(req)))

    def addAck(self, msg: Any, sender: str):
        idr = msg[f.IDENTIFIER.nm]
        reqId = msg[f.REQ_ID.nm]
        key = "{}{}".format(idr, reqId)
        self.reqStore.appendToValue(key, "A:{}".format(sender))

    def addNack(self, msg: Any, sender: str):
        idr = msg[f.IDENTIFIER.nm]
        reqId = msg[f.REQ_ID.nm]
        key = "{}{}".format(idr, reqId)
        reason = msg[f.REASON.nm]
        self.reqStore.appendToValue(key, "N:{}:{}".
                                    format(sender, reason))

    def addReply(self, identifier: str, reqId: int, sender: str,
                 result: Any) -> Sequence[str]:
        serializedReply = self.txnSerializer.serialize(result, toBytes=False)
        key = "{}{}".format(identifier, reqId)
        self.reqStore.appendToValue(key,
                                    "R:{}:{}".format(sender, serializedReply))
        return len(self._getSerializedReplies(identifier, reqId))

    def hasRequest(self, identifier: str, reqId: int) -> bool:
        key = '{}{}'.format(identifier, reqId)
        return self.reqStore.exists(key)

    def getRequest(self, identifier: str, reqId: int) -> Request:
        for r in self._getLinesWithPrefix(identifier, reqId, "0:"):
            return self.deserializeReq(r[2:])

    def getReplies(self, identifier: str, reqId: int):
        replies = self._getSerializedReplies(identifier, reqId)
        for sender, reply in replies.items():
            replies[sender] = self.txnSerializer.deserialize(reply)
        return replies

    def getAcks(self, identifier: str, reqId: int) -> List[str]:
        ackLines = self._getLinesWithPrefix(identifier, reqId, "A:")
        return [line[2:] for line in ackLines]

    def getNacks(self, identifier: str, reqId: int) -> dict:
        nackLines = self._getLinesWithPrefix(identifier, reqId, "N:")
        result = {}
        for line in nackLines:
            sender, reason = line[2:].split(":", 1)
            result[sender] = reason
        return result

    @property
    def txnFieldOrdering(self):
        fields = getTxnOrderedFields()
        return updateFieldsWithSeqNo(fields)

    @staticmethod
    def serializeReq(req: Request) -> str:
        return json.dumps(req.__getstate__())

    @staticmethod
    def deserializeReq(serReq: str) -> Request:
        return Request.fromState(json.loads(serReq))

    def _getLinesWithPrefix(self, identifier: str, reqId: int,
                            prefix: str) -> List[str]:
        key = '{}{}'.format(identifier, reqId)
        data = self.reqStore.get(key)
        return [line for line in data.split(os.linesep)
                if line.startswith(prefix)] if data else []

    def _getSerializedReplies(self, identifier: str, reqId: int) -> \
            Dict[str, str]:
        replyLines = self._getLinesWithPrefix(identifier, reqId, "R:")
        result = {}
        for line in replyLines:
            sender, reply = line[2:].split(":", 1)
            result[sender] = reply
        return result


