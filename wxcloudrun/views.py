import datetime
import json
import threading

import gevent
from flask import request
from gevent.queue import Queue, Empty
from simple_websocket import Server

from run import app
from wxcloudrun import sock
from wxcloudrun.response import make_succ_empty_response, make_succ_response

roomMap = {}


class SocketQueue(Queue):
    def __init__(self, uid):
        super().__init__()
        self.uid = uid


@sock.route('/wsx')
def wsx(ws: Server):
    # The ws object has the following methods:
    # - ws.send(data)
    # - ws.receive(timeout=None)
    # - ws.close(reason=None, message=None)
    roomId = request.values.get("roomId")
    userId = request.values.get("userId")
    if roomId is None or userId is None:
        ws.send("参数为空，连接断开")
        logWarn("参数为空，连接断开")
        return
    queue = SocketQueue(userId)
    try:
        # 加入房间
        if roomId in roomMap:
            roomMap[roomId].append(queue)
        else:
            roomMap[roomId] = [queue]
        while True:
            try:
                item = queue.get(timeout=1)
                if item is not None:
                    ws.send(item)
            except Empty:
                pass
            data = ws.receive(timeout=0)
            if data is not None:  # 收
                if data == 'close':
                    logWarn(f"receive:close:{datetime.datetime.now()}")
                    break
                elif data == 'ping':
                    ws.send('pong')
                else:
                    ws.send(data)
            gevent.sleep(0)
    except Exception as e:
        logWarn(f"{roomId}-{userId}-socket 断开：{e}")
    finally:
        if roomId in roomMap:
            # 退出房间
            if roomMap[roomId].__contains__(queue):
                roomMap[roomId].remove(queue)
            # 清空 map 的 key
            if len(roomMap[roomId]) == 0:
                del roomMap[roomId]
        if ws.connected:
            logWarn(f"finally close:{datetime.datetime.now()}")
            ws.close()


@sock.route('/notifyWsx')
def wsx(ws: Server):
    try:
        while True:
            data = ws.receive()
            if data == 'close':
                break
            else:
                try:
                    js = json.loads(data)
                    _type = js['ty']  # type  1,通知 2，释放
                    if _type == 1:
                        roomId = js['rid']  # roomId
                        userId = js['uid']  # userId
                        latestWasteId = js['lid']  # latestWasteId
                        notifyRoomChange(roomId, userId, latestWasteId)
                    elif _type == 2:
                        roomId = js['rid']  # roomId
                        releaseRoomConnect(roomId)
                except Exception as e:
                    logWarn(f"notifyWsx-js Exception：{e}")
    except Exception as e:
        logWarn(f"notifyWsx-Exception 断开：{e}")
    finally:
        if ws.connected:
            ws.close()


@app.route('/testNotify')
def testNotify():
    try:
        roomId = request.values.get("roomId")
        queueList = roomMap.get(roomId)
        if queueList is not None:
            for q in queueList:
                q.put({'ll': 100, 'uu': 200})
        return make_succ_empty_response()
    except Exception as e:
        logInfo(e)


@app.route('/getRoomSocketInfo')
def getRoomSocketInfo():
    try:
        logWarn(f"Current thread ID: {threading.get_ident()}")
        logWarn(f"Current coroutine: {gevent.getcurrent()}")
        logWarn(f"roomMap:{roomMap}")
        roomId = request.values.get("roomId")
        queueList = roomMap.get(roomId)
        wsListInfo = []
        if queueList is not None:
            logWarn(f'getRoomSocketInfo:wsList len:{len(queueList)}')
            for q in queueList:
                wsListInfo.append({"userId": q.uid})
        else:
            logWarn(f'getRoomSocketInfo:wsList 为 none')
        return make_succ_response(wsListInfo)
    except Exception as e:
        logInfo(f'getRoomSocketInfo exception:{e}')


def releaseRoomConnect(roomId):
    queueList = roomMap.get(f'{roomId}')
    if queueList is not None:
        queueList.clear()
        del roomMap[f'{roomId}']


def notifyRoomChange(roomId, userId, latestWasteId):
    try:
        queueList = roomMap.get(f'{roomId}')
        if queueList is not None:
            for q in queueList:
                q.put(json.dumps({"l": latestWasteId, "u": userId}))
    except Exception as e:
        logInfo(f'notifyRoomChange exception:{e}')


@app.route('/api/notifyRoomWs', methods=['POST'])
def notifyRoomWs():
    # 获取请求体参数
    try:
        params = request.get_json()
        roomId = params['roomId']
        userId = params['userId']
        latestWasteId = params['latestWasteId']
        notifyRoomChange(roomId, userId, latestWasteId)
        return make_succ_empty_response()
    except Exception as e:
        logInfo(f'notifyRoom exception:{e}')


@app.route('/api/releaseRoomWs', methods=['POST'])
def releaseRoomWs():
    # 获取请求体参数
    try:
        params = request.get_json()
        roomId = params['roomId']
        releaseRoomConnect(roomId)
        return make_succ_empty_response()
    except Exception as e:
        logInfo(f'releaseRoom exception:{e}')


def logInfo(msg):
    app.logger.warn(msg)


def logWarn(msg):
    app.logger.warn(msg)


@app.route('/')
def index():
    logWarn(f'index  {threading.current_thread().name}')
    return make_succ_empty_response()


def is_float(s):
    try:  # 如果能运行float(s)语句，返回True（字符串s是浮点数）
        float(s)
        return True
    except ValueError:  # ValueError为Python的一种标准异常，表示"传入无效的参数"
        pass  # 如果引发了ValueError这种异常，不做任何事情（pass：不做任何事情，一般用做占位语句）
    return False
