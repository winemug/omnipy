from pymongo.collection import Collection
from pymongo.command_cursor import CommandCursor
from pymongo.cursor import Cursor, CursorType


def mongo_aggregate(coll: Collection, pipeline) -> []:
    return mongo_result(coll.aggregate(pipeline))


def mongo_find(coll: Collection, query, sort=None, projection=None) -> []:
    return mongo_result(coll.find(filter=query, sort=sort, projection=projection, cursor_type=CursorType.EXHAUST))


def mongo_result(cc: Cursor) -> []:
    ret = []
    with cc:
        for r in cc:
            ret.append(r)
    return ret
