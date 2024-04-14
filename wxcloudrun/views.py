import datetime
import json
import random
import threading

import gevent
import requests
from flask import render_template, request
from flask_apscheduler import APScheduler
from gevent.queue import Queue, Empty
from simple_websocket import Server

from run import app
from wxcloudrun import dao, sock, db, serverMsgQueue
from wxcloudrun.dao import delete_counterbyid, query_counterbyid, insert_counter, update_counterbyid, insert_room, update_room_qr_byid, \
    query_user_by_openid, insert_user, update_user_by_id
from wxcloudrun.model import Counters, Room, User, RoomWasteBook
from wxcloudrun.response import make_succ_empty_response, make_succ_response, make_err_response

# 定时任务
scheduler = APScheduler()


@scheduler.task('interval', start_date=datetime.datetime.now() + datetime.timedelta(minutes=5), id='do_job_2',
                minutes=60)
def clearTask():
    with db.app.app_context():
        logInfo(f'定时任务-开始clear  {threading.current_thread().name}')
        clearRoom()
        logInfo(f'定时任务-结束clear  {threading.current_thread().name}')


scheduler.init_app(app)
scheduler.start()
# 定时任务 = end =

words = "12356789"
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
    serverMsgQueue.put({"ty": 2, "rid": roomId})
    # queueList = roomMap.get(f'{roomId}')
    # if queueList is not None:
    #     queueList.clear()
    #     del roomMap[f'{roomId}']


def notifyRoomChange(roomId, userId, latestWasteId):
    try:
        serverMsgQueue.put({"ty": 1, "rid": roomId, "uid": userId, "lid": latestWasteId})
        # queueList = roomMap.get(f'{roomId}')
        # if queueList is not None:
        #     for q in queueList:
        #         q.put(json.dumps({"l": latestWasteId, "u": userId}))
    except Exception as e:
        logInfo(f'notifyRoomChange exception:{e}')


# 清理房间
@app.route('/testclear')
def testclear():
    clearRoom()
    return make_succ_empty_response()


def clearRoom():
    logInfo(f'clearRoom - {threading.current_thread().name}')
    # 查询使用时长 > 3小时的 在使用中的房间
    flagTime = datetime.datetime.now() - datetime.timedelta(hours=3)
    rooms = dao.query_using_room_by_usetime(flagTime)
    if rooms is None:
        logInfo(f'flagTime:{flagTime} - rooms:null')
        return
    logInfo(f'flagTime:{flagTime} - rooms:{len(rooms)}')
    for r in rooms:
        latestWaste = dao.get_latest_wastes_from_room(r.id)
        if latestWaste is not None:
            logInfo(f'开始清理房间 roomId:{r.id} -- name:{r.name} -- latestWasteTime:{latestWaste.time} -start--')
        else:
            logInfo(f'开始清理房间 roomId:{r.id} -- name:{r.name} -- latestWasteTime:null -start--')
        if latestWaste is None or latestWaste.time < flagTime:
            # 开始清理房间  
            userScores = {}
            if latestWaste is not None:  # 存在最后一条数据才可能存在更多流水
                wlist = dao.get_outlay_wastes_from_room(r.id)
                if wlist is not None:
                    for w in wlist:
                        userScores[f'{w.outlay_user_id}'] = userScores.get(f'{w.outlay_user_id}', 0) - w.score
                        userScores[f'{w.receive_user_id}'] = userScores.get(f'{w.receive_user_id}', 0) + w.score
            logInfo(f'userScores:{userScores}')
            dao.autoReleaseRoom(r.id, userScores)
            # 移除 websocket 连接
            releaseRoomConnect(r.id)
            logInfo(f'{r.id} -- {r.name}---end--')
    

def logInfo(msg):
    app.logger.warn(msg)


def logWarn(msg):
    app.logger.warn(msg)


@app.route('/')
def index():
    dao.query_using_room_by_usetime(datetime.datetime.now())
    logWarn(f'index  {threading.current_thread().name}')
    """
    :return: 返回index页面
    """
    return render_template('index.html')


@app.route('/api/count', methods=['POST'])
def count():
    """
    :return:计数结果/清除结果
    """

    # 获取请求体参数
    params = request.get_json()

    # 检查action参数
    if 'action' not in params:
        return make_err_response('缺少action参数')

    # 按照不同的action的值，进行不同的操作
    action = params['action']

    # 执行自增操作
    if action == 'inc':
        counter = query_counterbyid(1)
        if counter is None:
            counter = Counters()
            counter.id = 1
            counter.count = 1
            counter.created_at = datetime.datetime.now()
            counter.updated_at = datetime.datetime.now()
            insert_counter(counter)
        else:
            counter.id = 1
            counter.count += 1
            counter.updated_at = datetime.datetime.now()
            update_counterbyid(counter)
        return make_succ_response(counter.count)

    # 执行清0操作
    elif action == 'clear':
        delete_counterbyid(1)
        return make_succ_empty_response()

    # action参数错误
    else:
        return make_err_response('action参数错误')


@app.route('/api/count', methods=['GET'])
def get_count():
    """
    :return: 计数的值
    """
    counter = Counters.query.filter(Counters.id == 1).first()
    return make_succ_response(0) if counter is None else make_succ_response(counter.count)


def addUserToRoom(user, room):
    # logInfo(f'addUserToRoom(userId:{user.id},roomId:{room.id})')
    dao.add_user_to_room(user.id, room.id)
    dao.updateUserLatestRoomId(user.id, room.id)
    # 插入房间流水记录
    roomWasteBook = RoomWasteBook(room_id=room.id, user_id=user.id, user_nickname=user.nickname, user_avatar_url=user.avatar_url, type=2,
                                  time=datetime.datetime.now())
    dao.add_waste_to_room(roomWasteBook)
    # notify
    notifyRoomChange(room.id, user.id, roomWasteBook.id)


def getRoomDetail(room):
    wastes = getRoomNewRecords(room.id, 0)
    data = {"roomId": room.id, "roomName": room.name, "shareQrUrl": room.share_qr, "wasteList": wastes}
    return make_succ_response(data)


@app.route('/api/openRoom', methods=['POST'])
def open_room():
    """
    我要开房
    :return: 房间信息xxx
    """
    userId = int(request.values.get("userId"))
    myapp = request.values.get("myapp")
    if myapp is None:
        myapp = "100"
    room = getCacheRoom(myapp)
    user = dao.query_user_by_id(userId)
    addUserToRoom(user, room)
    return getRoomDetail(room)


def removeUserFromRoom(userId, latestRoomId):
    logInfo(f'removeUserFromRoom userId:{userId} latestRoomId:{latestRoomId}')
    # 更新个人总得分 todo 不一定每次退出都要更新的
    dao.rm_user_from_room_and_update_settle_score(userId, latestRoomId)
    # dao.rm_user_from_room(userId, latestRoomId) #
    dao.updateUserLatestRoomId(userId, 0)

    # 插入房间流水记录
    user = dao.query_user_by_id(userId)
    roomWasteBook = RoomWasteBook(room_id=latestRoomId, user_id=user.id, user_nickname=user.nickname, user_avatar_url=user.avatar_url, type=3,
                                  time=datetime.datetime.now())
    dao.add_waste_to_room(roomWasteBook)

    notifyRoomChange(latestRoomId, userId, roomWasteBook.id)


# 进入房间
@app.route('/api/enterRoom', methods=['POST'])
def enter_room():
    """
    进入开房
    :return: 房间信息xxx
    """

    userId = int(request.values.get("userId"))
    roomIdStr = request.values.get("roomId")

    user = dao.query_user_by_id(userId)
    latestRoomId = user.latest_room_id
    logWarn(f'api:enterRoom -- userId:{userId} -- newRoomId:{roomIdStr} -- oldRoomId:{latestRoomId}')
    if roomIdStr is not None and len(roomIdStr) > 0 and roomIdStr != 'undefined':  # 存在新的 room
        newRoomId = int(roomIdStr)
        newRoom = dao.query_using_roombyid(newRoomId)
        if newRoom is not None:  # 新的 room 有效
            if user.latest_room_id == 0:  # 新进入
                addUserToRoom(user, newRoom)
                return getRoomDetail(newRoom)
            elif user.latest_room_id == newRoomId:  # 已经在新的房间了，直接返回
                return getRoomDetail(newRoom)
            else:  # 存在老的房间
                # 判断老的房间是否需要结算，如果需要结算则先进入到老的房间
                latestRoom = dao.query_using_roombyid(latestRoomId)
                if latestRoom is not None:
                    # 判断是否需要结算
                    wastes = dao.get_wastes_from_room_by_latestid(latestRoomId, 0)
                    userScores = {}
                    calculateScore(userScores=userScores,userStatus={}, wastes=wastes,curTeaFeeAmount=0, curTeaFeeLimit=-1,curTeaFeeRatio=0)
                    if userScores.get(f'{userId}', 0) != 0:  # 需要结算,先进入老的房间，结算完后提示可以进入新的房间
                        return make_succ_response({"roomId": latestRoom.id, "roomName": latestRoom.name, "shareQrUrl": latestRoom.share_qr,
                                                   "wasteList": wasteConvertToJsonList(wastes), "newRoomId": newRoomId, "newRoomName": newRoom.name})

                # 先退出之前的房间
                removeUserFromRoom(userId, latestRoomId)
                # 进入新的房间
                addUserToRoom(user, newRoom)
                return getRoomDetail(newRoom)
        else:  # 新的 room 无效
            if latestRoomId != 0:
                latestRoom = dao.query_using_roombyid(latestRoomId)
                if latestRoom is not None:
                    return getRoomDetail(latestRoom)
    else:  # 正常进入房间
        if latestRoomId != 0:
            room = dao.query_using_roombyid(user.latest_room_id)
            if room is not None:
                return getRoomDetail(room)
    return make_err_response("已退出房间或房间已关闭")


def getCacheRoom(myapp):
    room = dao.get_empty_room_and_update_status(myapp)
    if room is None:
        room = createRoom(myapp, 1)
    return room


def createRoom(myapp,status):
    if status == 1:
        room = Room(name=randomRoomName(), status=status, created_at=datetime.datetime.now(), use_at=datetime.datetime.now(), user_ids=[],myapp=myapp)
    else:
        room = Room(name=randomRoomName(), status=status, created_at=datetime.datetime.now(), user_ids=[], myapp=myapp)
    insert_room(room)
    qrcodeUrl = getQrCode(myapp,room.id, room.name)
    update_room_qr_byid(room.id, qrcodeUrl)
    return room


# 批量生产房间
# todo:remove route
@app.route('/api/batchCreateRoom', methods=['POST'])
def batchCreateRoom():
    for i in range(1, 500):
        createRoom("100", 0)

@app.route('/api/batchCreateRoom101', methods=['POST'])
def batchCreateRoom101():
    for i in range(1, 500):
        createRoom("101", 0)


def appSecret(myapp):
    if myapp == "100":
        return "35c80409f56b5ec27b8867176426657b"
    else:
        return "0d8259d1bc013a32c605a45f8e8f104f"


def appId(myapp):
    if myapp == "100":
        return "wx6f6f3e6f46e9d199"
    else:
        return "wxc9afbf53652df0ec"


def getQrCode(myapp, roomId, roomName):
    qrImg = requests.post(url=f"http://api.weixin.qq.com/wxa/getwxacodeunlimit?from_appid={appId(myapp)}",
                          json={"page": "pages/index/index", "scene": f"roomId={roomId}&myapp={myapp}", "width": 300, "check_path": False})

    # 上传到对象服务器
    # prod-3gvgzn5xf978a9ac
    print("---------getQrCode------------")
    # 1、获取上传地址
    tempFilePath = f"qrcode/{roomName}-{roomId}.png"
    uploadInfo = requests.post(url=f"http://api.weixin.qq.com/tcb/uploadfile", json={
        "env": "prod-3gvgzn5xf978a9ac",
        "path": tempFilePath
    })
    uploadInfoJson = json.loads(uploadInfo.content)
    # 2、开始上传

    # files = {'file': open(tempFilePath, 'rb')}
    files = {'file': qrImg.content}
    data = {"key": tempFilePath, "Signature": uploadInfoJson["authorization"], "x-cos-security-token": uploadInfoJson["token"],
            "x-cos-meta-fileid": uploadInfoJson["cos_file_id"]}
    requests.post(uploadInfoJson["url"], data=data, files=files)

    # 3、获取下载地址
    downloadResp = requests.post(url=f"http://api.weixin.qq.com/tcb/batchdownloadfile", json={
        "env": "prod-3gvgzn5xf978a9ac",
        "file_list": [
            {
                "fileid": uploadInfoJson["file_id"],
                "max_age": 7200
            }
        ]
    })
    downloadUrl = json.loads(downloadResp.content)['file_list'][0]['download_url']
    # if uploadInfoJson.get('errcode') == 0:
    #     return uploadInfoJson.get('file_id')
    return downloadUrl


@app.route('/api/login', methods=['POST'])
def login():
    # 获取请求体参数
    # APPID = "wx6f6f3e6f46e9d199"
    # SECRET = "35c80409f56b5ec27b8867176426657b"

    # 获取请求体参数
    params = request.get_json()
    logWarn(f'login:{params}')
    code = params.get("code")
    userId = params.get("userId")
    myapp = params.get("myapp")
    if myapp is None:
        myapp = "100"
    if myapp == "100":
        APPID = "wx6f6f3e6f46e9d199"
        SECRET = "35c80409f56b5ec27b8867176426657b"
    else:
        APPID = "wxc9afbf53652df0ec"
        SECRET = "0d8259d1bc013a32c605a45f8e8f104f"

    if userId is not None:
        user = dao.query_user_by_id(userId)
        if user is not None:
            return make_succ_response({"id": user.id, "nickname": user.nickname, "avatar_url": user.avatar_url, "isNewUser": 0})
        else:
            logInfo(f"userId: {userId} 用户不存在")
            return make_err_response("用户不存在")
    elif code is not None:
        resp = requests.get(
            url=f"http://api.weixin.qq.com/sns/jscode2session?appid={APPID}&secret={SECRET}&js_code={code}&grant_type=authorization_code")
        # {
        # "openid":"xxxxxx",
        # "session_key":"xxxxx",
        # "unionid":"xxxxx",
        # "errcode":0,
        # "errmsg":"xxxxx"
        # }
        #
        jsonData = resp.json()
        if jsonData.get('openid') is not None:
            openId = jsonData['openid']
            # 返回用户信息
            user = query_user_by_openid(openId,myapp)
            isNewUser = 0
            if user is None:
                user = User(wx_unionid=jsonData.get('unionid'), wx_openid=openId, wx_session_key=jsonData.get('session_key'), latest_room_id=0,
                            myapp=myapp, time=datetime.datetime.now())
                insert_user(user)
                isNewUser = 1  # 新用户
            return make_succ_response({"id": user.id, "nickname": user.nickname, "avatar_url": user.avatar_url, "isNewUser": isNewUser})
        else:
            logInfo(f"登录失败:{jsonData.get('errcode')}  {jsonData.get('errmsg')}")
            return make_err_response(jsonData.get('errmsg'))
    else:
        return make_err_response("参数错误")


@app.route('/api/updateProfile', methods=['POST'])
def updateProfile():
    # 获取请求体参数
    params = request.get_json()
    logInfo(f'updateProfile:{params}')
    userid = params['userid']
    nickname = params['nickname']
    avatarUrl = None
    avatarFileId = None
    if 'avatarUrl' in params:
        avatarUrl = params['avatarUrl']
        avatarFileId = params['avatarFileId']
    # 返回用户信息
    updateUser = update_user_by_id(userid, nickname, avatarUrl, avatarFileId)
    if updateUser is not None:
        # 查询当前用户所在的房间

        curRoomId = dao.query_using_roomid_by_uid(userid)
        if curRoomId is not None:  # 在房间中
            # 插入房间流水记录
            roomWasteBook = RoomWasteBook(room_id=curRoomId, user_id=userid, user_nickname=nickname, user_avatar_url=updateUser.avatar_url, type=5,
                                          time=datetime.datetime.now())
            dao.add_waste_to_room(roomWasteBook)
            # notify
            notifyRoomChange(curRoomId, userid, roomWasteBook.id)

    return make_succ_response("success")


@app.route('/api/getQrCode', methods=['POST'])
def get_qrcode():
    """
    :return: 获取分享二维码
    """

    roomId = "396"
    roomName = "OAI"

    return make_succ_response(getQrCode('100', roomId, roomName))

    # ROOT_PATH = os.path.dirname(__file__)
    # new_file_name = os.path.join(f"{ROOT_PATH}/static/images","xx.png")
    #
    # with open('new_imag.png','wb') as f:
    #     f.write(resp.content)


    # img_stream = str(base64.b64encode(resp.content),'utf-8')



    # img = Image.new('RGB', (100, 100), color=(255, 0, 0))
    # img_io = BytesIO()
    # img.raw.save(img_io, 'JPEG', quality=70)
    # img_io.seek(0)
    # return send_file(img_io, mimetype='image/jpeg')

    # render_template()
    # Response(resp.raw, mimetype='application/json')
    # return make_succ_response(0)


def randomRoomName():
    terms = ''
    for _ in range(5):
        terms = terms + str(random.sample(words, 1)[0])
    return terms


def wasteConvertToJsonList(wastes):
    wasteList = []
    for w in wastes:
        wasteList.append(
            {"id": w.id, "roomId": w.room_id, "outlayUserId": w.outlay_user_id, "receiveUserId": w.receive_user_id, "score": w.score, "type": w.type,
             "userId": w.user_id, "userNickname": w.user_nickname, "userAvatarUrl": w.user_avatar_url, "settleInfo": w.settle_info, "msg": w.msg,
             "teaRatio":w.tea_ratio,"teaLimit":w.tea_limit, "time": w.time.strftime('%Y-%m-%dT%H:%M:%S')})
    return wasteList


def getRoomNewRecords(roomId, latestWasteId):
    wastes = dao.get_wastes_from_room_by_latestid(roomId, latestWasteId)
    return wasteConvertToJsonList(wastes)


# 刷新房间
@app.route('/api/refreshRoom', methods=['POST'])
def refreshRoom():
    # 获取请求体参数
    params = request.get_json()
    roomId = params['roomId']
    latestWasteId = params['latestWasteId']
    return make_succ_response(getRoomNewRecords(roomId, latestWasteId))


def is_float(s):
    try:  # 如果能运行float(s)语句，返回True（字符串s是浮点数）
        float(s)
        return True
    except ValueError:  # ValueError为Python的一种标准异常，表示"传入无效的参数"
        pass  # 如果引发了ValueError这种异常，不做任何事情（pass：不做任何事情，一般用做占位语句）
    return False


# 支付分数
@app.route('/api/outlayScore', methods=['POST'])
def outlayScore():
    # 获取请求体参数
    params = request.get_json()
    outlayUserId = params['outlayUserId']
    receiveInfo = params['receiveInfo']
    roomId = params['roomId']
    latestWasteId = params['latestWasteId']
    wastes = []
    for ruid in receiveInfo:
        if is_float(receiveInfo[ruid]):  # 兼容前端未做的校验
            wastes.append(RoomWasteBook(room_id=roomId, outlay_user_id=outlayUserId, receive_user_id=int(ruid), score=receiveInfo[ruid], type=1,
                                        time=datetime.datetime.now()))
    if len(wastes) == 0: # 没有数据，兼容异常情况
        return make_err_response("未输入有效支付分")
    dao.add_all_wastes_to_room(wastes)
    # 返回最新的房间流水，由前端进行计算
    wastes = getRoomNewRecords(roomId, latestWasteId)
    notifyRoomChange(roomId, outlayUserId, wastes[len(wastes) - 1]['id'])
    return make_succ_response({"roomId": roomId, "wasteList": wastes})


# 直接向茶水支付分数
@app.route('/api/outlayTeaScore', methods=['POST'])
def outlayTeaScore():
    # 获取请求体参数
    params = request.get_json()
    roomId = params['roomId']
    outlayUserId = params['outlayUserId']
    latestWasteId = params['latestWasteId']
    score = params['score']
    curTeaFeeLimit = params['curTeaFeeLimit']
    curTeaFeeAmount = params['curTeaFeeAmount']
    curTeaFeeRatio = params['curTeaFeeRatio']
    userStatus = params['userStatus']
    logInfo(f"outlayTeaScore:{params}")

    #  计算当前的已经累计的 茶水费
    wasteList = dao.get_wastes_from_room_by_latestid(roomId, latestWasteId)
    curTeaFeeLimit, curTeaFeeRatio, curTeaFeeAmount = calculateTeaFeeAmount(userStatus,curTeaFeeLimit, curTeaFeeRatio,
                                                                            curTeaFeeAmount, wasteList)
    bizCode = 0
    if curTeaFeeLimit != -1 and curTeaFeeAmount >= curTeaFeeLimit:  # 茶水费已经收齐
        bizCode = 10003
    if bizCode == 0:
        if is_float(score):  # 兼容前端未做的校验
            rwb = RoomWasteBook(room_id=roomId, outlay_user_id=outlayUserId, receive_user_id=-100, score=score,
                                type=1, time=datetime.datetime.now())
            dao.add_waste_to_room(rwb)
            wastes = getRoomNewRecords(roomId, latestWasteId)
            notifyRoomChange(roomId, outlayUserId, wastes[len(wastes) - 1]['id'])
            return make_succ_response({"roomId": roomId, "bizCode": bizCode,"curTeaFeeAmount":curTeaFeeAmount, "wasteList": wastes})
        else:
            bizCode = 10004  # 参数有问题
    return make_succ_response({"roomId": roomId, "bizCode": bizCode,"curTeaFeeAmount":curTeaFeeAmount, "wasteList": wasteConvertToJsonList(wasteList)})


# 算分
def calculateScore(userScores, userStatus,wastes,curTeaFeeAmount,curTeaFeeLimit,curTeaFeeRatio):
    theCurTeaFeeAmount = curTeaFeeAmount
    theCurTeaFeeLimit = curTeaFeeLimit
    theCurTeaFeeRatio = curTeaFeeRatio
    for w in wastes:
        if w.type == 1:  # 支付
            if w.receive_user_id != -100 and userStatus.get(f'{w.receive_user_id}', 0) == 0:  # 无效计分
                continue
            tempTeaFee = getTeaFeeFromWaste(w, theCurTeaFeeLimit, theCurTeaFeeRatio, theCurTeaFeeAmount)
            userScores['-100'] = userScores.get('-100', 0) + tempTeaFee
            if w.receive_user_id == -100: # 向茶水支付
                userScores[f'{w.outlay_user_id}'] = userScores.get(f'{w.outlay_user_id}', 0) - tempTeaFee
            else:
                userScores[f'{w.outlay_user_id}'] = userScores.get(f'{w.outlay_user_id}', 0) - w.score
                userScores[f'{w.receive_user_id}'] = userScores.get(f'{w.receive_user_id}', 0) + w.score - tempTeaFee
        elif w.type == 2:  # 进入
            userStatus[f'{w.user_id}'] = 1
        elif w.type == 3:  # 退出
            userStatus[f'{w.user_id}'] = 0
        elif w.type == 4:  # 个人结算
            settleInfo = json.loads(w.settle_info)
            for settle in settleInfo:
                userScores[f'{settle["outlayUserId"]}'] = userScores.get(f'{settle["outlayUserId"]}', 0) + settle['score']
                userScores[f'{settle["receiveUserId"]}'] = userScores.get(f'{settle["receiveUserId"]}', 0) - settle['score']
        elif w.type == 6: # 茶水设置
            theCurTeaFeeLimit = w.tea_limit
            theCurTeaFeeRatio = w.tea_ratio

# 结算
def settle(userScores, currentSettleUid: int):
    # 判断茶水是否参与结算
    isTeaNotParticipate = False # 默认参与
    if userScores.__contains__('-100') and userScores['-100'] != 0: # 是否包含茶水,茶水为0时正常结算就可以
        noZeroScoreCount = 0  # 非0分数
        for score in userScores.values():
            if score != 0:
                noZeroScoreCount = noZeroScoreCount + 1
        if noZeroScoreCount >= 3 :# 房间里有效结算人员（score !=0 ）大于等于2人时，茶水不参与结算
            isTeaNotParticipate = True

    curUidStr = str(currentSettleUid)
    settleMsg = []  # 结算结果
    sortedUserScores = sorted(userScores.items(), key=lambda kv: (kv[1], kv[0]))  # 结算策略，人均最小支付次数，最少人参与原则 两个人各支付一次>一个人支付两次
    if userScores[curUidStr] > 0:
        for sus in sortedUserScores:
            if isTeaNotParticipate and sus[0] == '-100':
                continue
            if sus[1] < 0:
                tempScore = userScores[curUidStr] + sus[1]
                if tempScore <= 0:  # 完成结算
                    settleMsg.append({"outlayUserId": int(sus[0]), "receiveUserId": currentSettleUid, "score": userScores[curUidStr]})
                    userScores[curUidStr] = 0
                    userScores[sus[0]] = tempScore
                    break
                else:
                    settleMsg.append({"outlayUserId": int(sus[0]), "receiveUserId": currentSettleUid, "score": abs(sus[1])})
                    userScores[curUidStr] = tempScore
                    userScores[sus[0]] = 0
    elif userScores[curUidStr] < 0:
        hasPositiveScore = False  # 有正的分数
        for index, (key, score) in enumerate(reversed(sortedUserScores)):
            if isTeaNotParticipate and key == '-100':
                continue
            tempScore = userScores[curUidStr] + score
            if score > 0:
                hasPositiveScore = True
                if tempScore >= 0:  # 完成结算
                    settleMsg.append({"outlayUserId": currentSettleUid, "receiveUserId": int(key), "score": abs(userScores[curUidStr])})
                    userScores[curUidStr] = 0
                    userScores[key] = tempScore
                    break
                else:
                    settleMsg.append({"outlayUserId": currentSettleUid, "receiveUserId": int(key), "score": score})
                    userScores[curUidStr] = tempScore
                    userScores[key] = 0
            elif score < 0: # 为0 则不参与结算
                if hasPositiveScore:
                    break
                if key != curUidStr:  # 排除自己
                    settleMsg.append({"outlayUserId": currentSettleUid, "receiveUserId": int(key),"score": abs(userScores[curUidStr])})
                    userScores[curUidStr] = 0
                    userScores[key] = tempScore
                    break
        # 判断是否已经完成结算
        if userScores[curUidStr] != 0:
            # 修改最后一条结算记录
            lastItem = settleMsg[len(settleMsg)-1]
            lastItem['score'] = lastItem['score'] + abs(userScores[curUidStr])
            userScores[str(lastItem['receiveUserId'])] = userScores[str(lastItem['receiveUserId'])]+userScores[curUidStr]
            userScores[curUidStr] = 0

        # for sus in reversed(sortedUserScores):
        #     if sus[1] > 0:
        #         tempScore = userScores[curUidStr] + sus[1]
        #         if tempScore >= 0:  # 完成结算
        #             settleMsg.append({"outlayUserId": currentSettleUid, "receiveUserId": int(sus[0]), "score": abs(userScores[curUidStr])})
        #             userScores[curUidStr] = 0
        #             userScores[sus[0]] = tempScore
        #             break
        #         else:
        #             settleMsg.append({"outlayUserId": currentSettleUid, "receiveUserId": int(sus[0]), "score": sus[1]})
        #             userScores[curUidStr] = tempScore
        #             userScores[sus[0]] = 0
    return settleMsg


# 房间结算
@app.route('/api/roomSettle', methods=['POST'])
def roomSettle():
    # 获取请求体参数
    params = request.get_json()
    userId = params['userId']
    roomId = params['roomId']
    latestWasteId = params['latestWasteId']
    userScores = params['userScores']
    userStatus = params['userStatus']
    curTeaFeeAmount = params['curTeaFeeAmount']
    curTeaFeeLimit = params['curTeaFeeLimit']
    curTeaFeeRatio = params['curTeaFeeRatio']
    logInfo(f"roomSettle:{params}")
    # 查询最新流水
    wastes = dao.get_wastes_from_room_by_latestid(roomId=roomId, latestWasteId=latestWasteId)
    # 算分
    calculateScore(userScores,userStatus, wastes, curTeaFeeAmount, curTeaFeeLimit, curTeaFeeRatio)
    # 循环结算
    settleInfo = []
    for i in range(8):  # 最多8个用户一个房间，输多的先结，因为茶水>=0 ,所以也适用  ，茶水不主动结算，只被动结算
        sortedUserScores = sorted(userScores.items(), key=lambda kv: (kv[1], kv[0]))
        if sortedUserScores[0][1] == 0:
            break
        msg = settle(userScores, sortedUserScores[0][0])
        settleInfo.extend(msg)
    return make_succ_response({"roomId": roomId, "settleInfo": settleInfo, "wasteList": wasteConvertToJsonList(wastes)})


# 个人结算
@app.route('/api/individualSettle', methods=['POST'])
def individualSettle():
    # 获取请求体参数
    params = request.get_json()
    userId = params['userId']
    roomId = params['roomId']
    latestWasteId = params['latestWasteId']
    userScores = params['userScores']
    userStatus = params['userStatus']
    curTeaFeeAmount = params['curTeaFeeAmount']
    curTeaFeeLimit = params['curTeaFeeLimit']
    curTeaFeeRatio = params['curTeaFeeRatio']
    logInfo(f"individualSettle:{params}")
    # 查询最新流水
    wastes = dao.get_wastes_from_room_by_latestid(roomId=roomId, latestWasteId=latestWasteId)
    # 算分
    calculateScore(userScores,userStatus, wastes,curTeaFeeAmount,curTeaFeeLimit,curTeaFeeRatio)
    # 结算

    settleMsg = settle(userScores, userId)
    if len(settleMsg) == 0:
        return make_err_response("不需要结算")

    roomWasteBook = RoomWasteBook(room_id=roomId, user_id=userId, type=4, settle_info=json.dumps(settleMsg), time=datetime.datetime.now())
    dao.add_waste_to_room(roomWasteBook)

    # 因为有插入操作，第二次查询最新流水
    wastes = getRoomNewRecords(roomId, latestWasteId)
    notifyRoomChange(roomId, userId, wastes[len(wastes) - 1]['id'])
    return make_succ_response({"roomId": roomId, "wasteList": wastes})

def getTeaFeeFromWaste(w,curTeaFeeLimit,curTeaFeeRatio,curTeaFeeAmount):
    tempFee = 0
    if w.type == 1:  # 支付
        if curTeaFeeLimit == -1 or curTeaFeeAmount < curTeaFeeLimit:
            if w.receive_user_id != -100:  # 非直接向茶水支付，进行自动抽茶水
                if curTeaFeeRatio > 0:
                    tempFee = round(w.score * curTeaFeeRatio / 100)
                    if tempFee == 0 and w.score >= 2:
                        tempFee = 1
            else:
                tempFee = w.score
            if curTeaFeeLimit != -1 and (tempFee + curTeaFeeAmount > curTeaFeeLimit):
                tempFee = curTeaFeeLimit - curTeaFeeAmount
    return tempFee


# 计算累计茶水
def calculateTeaFeeAmount(userStatus,curTeaFeeLimit, curTeaFeeRatio, curTeaFeeAmount, wastesList):
    for w in wastesList:
        if w.type == 1:  # 支付
            if w.receive_user_id != -100 and userStatus.get(f'{w.receive_user_id}', 0) == 0:  # 无效计分
                continue
            curTeaFeeAmount = curTeaFeeAmount + getTeaFeeFromWaste(w,curTeaFeeLimit,curTeaFeeRatio, curTeaFeeAmount)
        elif w.type == 2:  # 进入
            userStatus[f'{w.user_id}'] = 1
        elif w.type == 3:  # 退出
            userStatus[f'{w.user_id}'] = 0
        elif w.type == 6:  # 茶水设置
            curTeaFeeLimit = w.tea_limit
            curTeaFeeRatio = w.tea_ratio
    return curTeaFeeLimit,curTeaFeeRatio,curTeaFeeAmount



# 茶水设置
@app.route('/api/teaFeeSet', methods=['POST'])
def teaFeeSet():
    # 获取请求体参数
    params = request.get_json()
    userId = params['userId']
    roomId = params['roomId']
    latestWasteId = params['latestWasteId']
    teaRatio = params['teaRatio']
    teaLimit = params['teaLimit']
    userStatus = params['userStatus']
    curTeaFeeAmount = params['curTeaFeeAmount']
    curTeaFeeLimit = params['curTeaFeeLimit']
    curTeaFeeRatio = params['curTeaFeeRatio']
    logInfo(f"teaFeeSet:{params}")

    #  计算当前的已经累计的 茶水费
    wastesList = dao.get_wastes_from_room_by_latestid(roomId, latestWasteId)
    curTeaFeeLimit, curTeaFeeRatio, curTeaFeeAmount = calculateTeaFeeAmount(userStatus,curTeaFeeLimit, curTeaFeeRatio,
                                                                            curTeaFeeAmount, wastesList)
    bizCode = 0
    if teaLimit != -1 and teaLimit < curTeaFeeAmount:
        bizCode = 10001  # 设置的上限小于当前已经累计的茶水
    if teaLimit == curTeaFeeLimit and teaRatio == curTeaFeeRatio:
        bizCode = 10002  # 设置的值未发生改变，不需要重复设置

    if bizCode == 0:
        waste = RoomWasteBook(room_id=roomId, user_id=userId, tea_ratio=teaRatio, tea_limit=teaLimit,
                              type=6, time=datetime.datetime.now())
        dao.add_waste_to_room(waste)
        # 返回最新的房间流水，由前端进行计算
        wastes = getRoomNewRecords(roomId, latestWasteId)
        notifyRoomChange(roomId, userId, wastes[len(wastes) - 1]['id'])
        return make_succ_response({"roomId": roomId,"bizCode":bizCode,"curTeaFeeAmount": curTeaFeeAmount,"wasteList": wastes})
    return make_succ_response({"roomId": roomId, "bizCode":bizCode,"curTeaFeeAmount": curTeaFeeAmount, "wasteList": wasteConvertToJsonList(wastesList)})

# 添加茶水
@app.route('/api/addTeaFee', methods=['POST'])
def addTeaFee():
    # 获取请求体参数
    params = request.get_json()
    userId = params['userId']
    roomId = params['roomId']
    latestWasteId = params['latestWasteId']
    logInfo(f"addTeaFee:{params}")
    waste = RoomWasteBook(room_id=roomId, user_id=userId,type=7, time=datetime.datetime.now())
    dao.add_waste_to_room(waste)
    wastes = getRoomNewRecords(roomId, latestWasteId)
    notifyRoomChange(roomId, userId, wastes[len(wastes) - 1]['id'])
    return make_succ_response({"roomId": roomId,"wasteList": wastes})



# 退出房间
@app.route('/api/exitRoom', methods=['POST'])
def exit_room():
    # 获取请求体参数
    params = request.get_json()
    userId = params['userId']
    roomId = params['roomId']
    curTeaFeeAmount = params['curTeaFeeAmount']
    curTeaFeeLimit = params['curTeaFeeLimit']
    curTeaFeeRatio = params['curTeaFeeRatio']
    latestWasteId = params['latestWasteId']
    userScores = params['userScores']
    userStatus = params['userStatus']
    logInfo(f"exit_room:{params}")

    # 查询最新流水
    wastes = dao.get_wastes_from_room_by_latestid(roomId=roomId, latestWasteId=latestWasteId)
    # 算分
    calculateScore(userScores, userStatus,wastes,curTeaFeeAmount, curTeaFeeLimit, curTeaFeeRatio)

    # 验证分数是否为0
    if userScores.get(f'{userId}', 0) == 0:
        # 同意退出 
        removeUserFromRoom(userId, roomId)
        return make_succ_response({"roomId": roomId, "exit": 1})
    else:  # 返回最新数据
        return make_succ_response({"roomId": roomId, "exit": 0, "wasteList": wasteConvertToJsonList(wastes)})


# 查询房间历史
@app.route('/api/roomHistory', methods=['POST'])
def roomHistory():
    # 获取请求体参数
    params = request.get_json()
    logInfo(f"roomHistory:{params}")
    userId = params['userId']
    historys = dao.query_history_rooms_by_uid(userId)
    historyList = []
    for h in historys:
        historyList.append(
            {'id': h.id, 'roomId': h.room_id, 'roomName': h.room_name, 'settleAmount': h.settle_amount, 'time': h.time.strftime('%Y-%m-%dT%H:%M:%S')})
    return make_succ_response(historyList)


# 查询房间历史
@app.route('/api/roomHistory_v2', methods=['POST'])
def roomHistory_v2():
    # 获取请求体参数
    params = request.get_json()
    logInfo(f"roomHistory:{params}")
    userId = params['userId']
    historys = dao.query_history_rooms_by_uid(userId)
    historyList = []
    roomids = []
    for h in historys:
        roomids.append(h.room_id)
        historyList.append(
            {'id': h.id, 'roomId': h.room_id, 'roomName': h.room_name, 'settleAmount': h.settle_amount, 'time': h.time.strftime('%Y-%m-%dT%H:%M:%S')})
    queryRes = dao.query_room_member_by_roomids(roomids, userId)
    roomMembers = []
    if queryRes is not None:
        for rm in queryRes:
            roomMembers.append({'roomId': rm[0], 'nickname': rm[1]})
    return make_succ_response({"historyList": historyList, "roomMembers": roomMembers})


# 删除房间历史
@app.route('/api/deleteHistory', methods=['POST'])
def deleteHistory():
    # 获取请求体参数
    params = request.get_json()
    logInfo(f"roomHistory:{params}")
    userId = params['userId']
    roomId = params['roomId']
    if dao.delete_history_room_by_uid_roomid(userId,roomId):
        return make_succ_response({"deleteRes": 1})
    else:
        return make_succ_response({"deleteRes": 0})


# 查询个人的对战统计情况 todo 数据是否可以合到其它的接口
@app.route('/api/getAchievement', methods=['POST'])
def getAchievement():
    params = request.get_json()
    # logWarn(f'getAchievement:{json.dumps(params)}')
    userId = params['userId']
    res = dao.query_achievement_by_uid(userId)
    return make_succ_response(res)


# 查看房间是否已经关闭
@app.route('/api/fetchRoomStatus', methods=['POST'])
def fetchRoomStatus():
    params = request.get_json()
    roomId = params['roomId']
    room = dao.query_roombyid(roomId)
    if room is not None:
        return make_succ_response(room.status)
    else:
        logWarn(f'fetchRoomStatus error: {roomId}')
        return make_succ_response("")
