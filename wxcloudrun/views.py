import json
from datetime import datetime
import random

import requests

from flask import render_template, request, Response, send_file, after_this_request
# from PIL import Image

from run import app
from wxcloudrun import dao
from wxcloudrun.dao import delete_counterbyid, query_counterbyid, insert_counter, update_counterbyid, insert_room, update_room_qr_byid, \
    query_user_by_openid, insert_user, update_user_by_id
from wxcloudrun.model import Counters, Room, User,RoomWasteBook
from wxcloudrun.response import make_succ_empty_response, make_succ_response, make_err_response

words = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def logInfo(msg):
    app.logger.info(msg)

@app.route('/')
def index():
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
            counter.created_at = datetime.now()
            counter.updated_at = datetime.now()
            insert_counter(counter)
        else:
            counter.id = 1
            counter.count += 1
            counter.updated_at = datetime.now()
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
    logInfo(f'addUserToRoom(userId:{user.id},roomId:{room.id})')
    dao.add_user_to_room(user.id,room.id)
    dao.updateUserLatestRoomId(user.id, room.id)
    #插入房间流水记录
    roomWasteBook = RoomWasteBook(room_id=room.id,user_id=user.id,user_nickname=user.nickname,user_avatar_url=user.avatar_url,type=2,time=datetime.now())
    dao.add_waste_to_room(roomWasteBook)


def getRoomDetail(room):
    wastes = getRoomNewRecords(room.id,0)
    data = {"roomId": room.id, "roomName": room.name, "shareQrUrl": room.share_qr,"wasteList": wastes}
    app.logger.info(data)
    return make_succ_response(data)


@app.route('/api/openRoom', methods=['POST'])
def open_room():
    """
    我要开房
    :return: 房间信息xxx
    """
    userId = int(request.values.get("userId"))
    room = getCacheRoom()
    user = dao.query_user_by_id(userId)
    addUserToRoom(user, room)
    return getRoomDetail(room)


def removeUserFromRoom(userId, latestRoomId):
    logInfo(f'removeUserFromRoom userId:{userId} latestRoomId:{latestRoomId}')
    # 更新个人总得分 todo 不一定每次退出都要更新的
    dao.rm_user_from_room_and_update_settle_score(userId,latestRoomId)
    dao.rm_user_from_room(userId, latestRoomId) # todo remove
    dao.updateUserLatestRoomId(userId, 0)

    #插入房间流水记录
    user = dao.query_user_by_id(userId)
    roomWasteBook = RoomWasteBook(room_id=latestRoomId,user_id=user.id,user_nickname=user.nickname,user_avatar_url=user.avatar_url,type=3,time=datetime.now())
    
    dao.add_waste_to_room(roomWasteBook)



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
    app.logger.info(f'api:enterRoom -- userId:{userId} -- newRoomId:{roomIdStr} -- oldRoomId:{latestRoomId}')

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
                    #判断是否需要结算
                    wastes = dao.get_wastes_from_room_by_latestid(latestRoomId,0)
                    userScores = {}
                    calculateScore(userScores=userScores,wastes=wastes)
                    if userScores.get(f'{userId}',0) != 0: # 需要结算,先进入老的房间，结算完后提示可以进入新的房间
                        return make_succ_response({"roomId": latestRoom.id, "roomName": latestRoom.name, "shareQrUrl": latestRoom.share_qr,"wasteList": wastes,"newRoomId":newRoomId})

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

def getCacheRoom():
    room = dao.get_empty_room_and_update_status()
    if room is None:
        room = createRoom(1)
    return room


def createRoom(status):
    room = Room(name=randomRoomName(), status=status, created_at=datetime.now(),user_ids=[])
    insert_room(room)
    qrcodeUrl = getQrCode(room.id, room.name)
    update_room_qr_byid(room.id, qrcodeUrl)
    return room

# 批量生产房间
# todo:remove route
@app.route('/api/batchCreateRoom', methods=['POST'])
def batchCreateRoom():
    for i in range(1, 100):
        createRoom(0)

def getQrCode(roomId,roomName):
    qrImg = requests.post(url="http://api.weixin.qq.com/wxa/getwxacodeunlimit",
                          json={"page": "pages/index/index","scene": "a=1", "width": 300,"check_path": False})
    # print(qrImg.text)
    # 上传到对象服务器
    # prod-3gvgzn5xf978a9ac
    print("xin------------")
    # 1、获取上传地址
    tempFilePath = f"qrcode/{roomName}-{roomId}.png"
    uploadInfo = requests.post(url="http://api.weixin.qq.com/tcb/uploadfile", json={
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
    downloadResp = requests.post(url="http://api.weixin.qq.com/tcb/batchdownloadfile", json={
        "env": "prod-3gvgzn5xf978a9ac",
        "file_list": [
            {
                "fileid": uploadInfoJson["file_id"],
                "max_age": 7200
            }
        ]
    })
    downloadUrl = json.loads(downloadResp.content)['file_list'][0]['download_url']
    return downloadUrl

@app.route('/api/login', methods=['POST'])
def login():
    # 获取请求体参数
    APPID="wx6f6f3e6f46e9d199"
    SECRET="35c80409f56b5ec27b8867176426657b"
    
     # 获取请求体参数
    params = request.get_json()
    
    code = params.get("code")
    userId = params.get("userId")
    
    if userId is not None:
        user = dao.query_user_by_id(userId)
        if user is not None:
            return make_succ_response({"id":user.id,"nickname":user.nickname,"avatar_url":user.avatar_url})
        else:
            logInfo(f"userId: {userId} 用户不存在")
            return make_err_response("用户不存在")
    elif code is not None:
        resp = requests.get(url=f"http://api.weixin.qq.com/sns/jscode2session?appid={APPID}&secret={SECRET}&js_code={code}&grant_type=authorization_code")
        # {
        # "openid":"xxxxxx",
        # "session_key":"xxxxx",
        # "unionid":"xxxxx",
        # "errcode":0,
        # "errmsg":"xxxxx"
        # }
        #
        print(resp.text)
        jsonData = resp.json()
        if jsonData.get('openid') is not None:
            openId = jsonData['openid']
            # 返回用户信息
            user = query_user_by_openid(openId)
            if user is None:
                user = User(wx_unionid=jsonData.get('unionid'), wx_openid=openId, wx_session_key=jsonData.get('session_key'),latest_room_id=0)
                insert_user(user)
            return make_succ_response({"id":user.id,"nickname":user.nickname,"avatar_url":user.avatar_url})
        else:
            logInfo(f"登录失败:{jsonData.get('errcode')}  {jsonData.get('errmsg')}")
            return make_err_response(jsonData.get('errmsg'))
    else:
        return make_err_response("参数错误")


    


@app.route('/api/updateProfile', methods=['POST'])
def updateProfile():
    # 获取请求体参数
    params = request.get_json()
    logInfo(params)
    userid = params['userid']
    nickname = params['nickname']
    avatarUrl = None
    avatarFileId = None
    if 'avatarUrl' in params:
        avatarUrl = params['avatarUrl']
        avatarFileId = params['avatarFileId']
    # 返回用户信息
    update_user_by_id(userid, nickname, avatarUrl, avatarFileId)
    return make_succ_response("success")


@app.route('/api/getQrCode', methods=['POST'])
def get_qrcode():
    """
    :return: 获取分享二维码
    """

    roomId = "1"
    roomName = "XGF"


    return make_succ_response(getQrCode(roomId,roomName))


    # ROOT_PATH = os.path.dirname(__file__)
    # new_file_name = os.path.join(f"{ROOT_PATH}/static/images","xx.png")
    #
    # with open('new_imag.png','wb') as f:
    #     f.write(resp.content)
    # print(resp.text)

    # img_stream = str(base64.b64encode(resp.content),'utf-8')
    # print(img_stream)

    # print(resp.text)
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
    for _ in range(3):
        terms = terms + str(random.sample(words, 1)[0])
    return terms

def wasteConvertToJsonList(wastes):
    wasteList = []
    for w in wastes:
        wasteList.append({"id":w.id,"roomId":w.room_id,"outlayUserId":w.outlay_user_id,"receiveUserId":w.receive_user_id,"score":w.score,"type":w.type,"userId":w.user_id,"userNickname":w.user_nickname,"userAvatarUrl":w.user_avatar_url, "settleInfo":w.settle_info, "msg":w.msg,"time":w.time.strftime('%Y-%m-%d %H:%M:%S')})
    print(wasteList)
    return wasteList

def getRoomNewRecords(roomId,latestWasteId):
    wastes = dao.get_wastes_from_room_by_latestid(roomId,latestWasteId)
    return wasteConvertToJsonList(wastes)


# 支付分数
@app.route('/api/outlayScore', methods=['POST'])
def outlayScore():
    # 获取请求体参数
    params = request.get_json()
    outlayUserId = params['outlayUserId']
    receiveInfo=params['receiveInfo']
    roomId= params['roomId'] 
    latestWasteId = params['latestWasteId']
    wastes=[] 
    for ruid in receiveInfo:
        wastes.append(RoomWasteBook(room_id=roomId, outlay_user_id=outlayUserId, receive_user_id=int(ruid),score=receiveInfo[ruid],type=1),time=datetime.now())
    dao.add_all_wastes_to_room(wastes)
    # 返回最新的房间流水，由前端进行计算
    wastes = getRoomNewRecords(roomId,latestWasteId)
    return make_succ_response({"roomId": roomId, "wasteList": wastes})

# 算分
def calculateScore(userScores,wastes):
    for w in wastes:
        if w.type == 1: # 支付
            userScores[f'{w.outlay_user_id}']=userScores.get(f'{w.outlay_user_id}',0)-w.score
            userScores[f'{w.receive_user_id}']=userScores.get(f'{w.receive_user_id}',0)+w.score
        elif w.type == 4: # 个人结算
            settleInfo = json.loads(w.settle_info)
            for settle in settleInfo:
                userScores[f'{settle["outlayUserId"]}'] = userScores.get(f'{settle["outlayUserId"]}',0) + settle['score']
                userScores[f'{settle["receiveUserId"]}'] = userScores.get(f'{settle["receiveUserId"]}',0) - settle['score']

# 结算
def settle(userScores,currentSettleUid:int):
    curUidStr = str(currentSettleUid)
    settleMsg = [] # 结算结果
    sortedUserScores = sorted(userScores.items(), key=lambda kv: (kv[1], kv[0])) #结算策略，优先支付最多的
    if userScores[curUidStr] > 0:
        for sus in sortedUserScores:
            if sus[1] < 0:
                tempScore = userScores[curUidStr] + sus[1]
                if tempScore <= 0: # 完成结算
                    settleMsg.append({"outlayUserId":int(sus[0]),"receiveUserId":currentSettleUid,"score":userScores[curUidStr]})
                    userScores[curUidStr]=0
                    userScores[sus[0]]=tempScore
                    break
                else:
                    settleMsg.append({"outlayUserId":int(sus[0]),"receiveUserId":currentSettleUid,"score":abs(sus[1])})
                    userScores[curUidStr] = tempScore
                    userScores[sus[0]] = 0
    elif userScores[curUidStr] < 0: 
        for sus in reversed(sortedUserScores):  
            if sus[1] >0:
                tempScore = userScores[curUidStr] + sus[1]
                if tempScore >= 0: # 完成结算
                    settleMsg.append({"outlayUserId":currentSettleUid,"receiveUserId":int(sus[0]),"score":abs(userScores[curUidStr])})
                    userScores[curUidStr]=0
                    userScores[sus[0]]=tempScore
                    break
                else:
                    settleMsg.append({"outlayUserId":currentSettleUid,"receiveUserId":int(sus[0]),"score":sus[1]})
                    userScores[curUidStr] = tempScore
                    userScores[sus[0]]=0
    return settleMsg

# 房间结算
@app.route('/api/roomSettle', methods=['POST'])
def roomSettle():
    # 获取请求体参数
    params = request.get_json()
    userId = params['userId']
    roomId= params['roomId']
    latestWasteId = params['latestWasteId']
    userScores = params['userScores']
    logInfo(f"individualSettle:{params}")
    # 查询最新流水
    wastes = dao.get_wastes_from_room_by_latestid(roomId=roomId,latestWasteId=latestWasteId)
    # 算分
    calculateScore(userScores,wastes)
    # 循环结算
    settleInfo = []
    for i in range(8): # 最多8个用户一个房间
        sortedUserScores = sorted(userScores.items(), reverse=True, key=lambda kv: (kv[1], kv[0])) 
        if sortedUserScores[0][1] == 0:
            break
        msg = settle(userScores,sortedUserScores[0][0])
        settleInfo.extend(msg)
    return make_succ_response({"roomId": roomId,"settleInfo":settleInfo, "wasteList": wasteConvertToJsonList(wastes)})
    


# 个人结算
@app.route('/api/individualSettle', methods=['POST'])
def individualSettle():
    
     # 获取请求体参数
    params = request.get_json()
    userId = params['userId']
    roomId= params['roomId']
    latestWasteId = params['latestWasteId']
    userScores = params['userScores']
    logInfo(f"individualSettle:{params}")
    # 查询最新流水
    wastes = dao.get_wastes_from_room_by_latestid(roomId=roomId,latestWasteId=latestWasteId)
    # 算分
    calculateScore(userScores,wastes)
    # 结算

    settleMsg = settle(userScores,userId)
    if len(settleMsg) == 0:
        return make_err_response("不需要结算")

    roomWasteBook = RoomWasteBook(room_id=roomId,user_id=userId,type=4,settle_info=json.dumps(settleMsg),time=datetime.now())
    dao.add_waste_to_room(roomWasteBook)
    
    # 因为有插入操作，第二次查询最新流水
    wastes = getRoomNewRecords(roomId,latestWasteId)
    return make_succ_response({"roomId": roomId, "wasteList": wastes})

# 退出房间
@app.route('/api/exitRoom', methods=['POST'])
def exit_room():
     # 获取请求体参数
    params = request.get_json()
    userId = params['userId']
    roomId= params['roomId']
    latestWasteId = params['latestWasteId']
    userScores = params['userScores']
    logInfo(f"individualSettle:{params}")

    # 查询最新流水
    wastes = dao.get_wastes_from_room_by_latestid(roomId=roomId,latestWasteId=latestWasteId)
    # 算分
    calculateScore(userScores,wastes)
    
    # 验证分数是否为0
    if userScores[f'{userId}'] == 0: 
        # 同意退出 
        removeUserFromRoom(userId, roomId)
        return make_succ_response({"roomId": roomId,"exit":1})
    else: #  返回最新数据
        return make_succ_response({"roomId": roomId,"exit":0,"wasteList": wastes})
    
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
        historyList.append({'id':h.id,'roomId':h.room_id,'roomName':h.room_name,'settleAmount':h.settle_amount,'time':h.time.strftime('%Y-%m-%dT%H:%M:%S')})
    return make_succ_response(historyList)

# 查询个人的对战统计情况 todo 数据是否可以合到其它的接口
@app.route('/api/getAchievement', methods=['POST'])
def getAchievement():
    params = request.get_json()
    logInfo(f"roomHistory:{params}")
    userId = params['userId']
    res = dao.query_achievement_by_uid(userId)
    return make_succ_response(res)
