import json
import logging
import time
from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.attributes import flag_modified

from wxcloudrun import db
from wxcloudrun.model import Counters, Room, User, RoomWasteBook, RoomMemberInfo, GameInfo

# 初始化日志
logger = logging.getLogger('log')


def query_counterbyid(id):
    """
    根据ID查询Counter实体
    :param id: Counter的ID
    :return: Counter实体
    """
    try:
        return Counters.query.filter(Counters.id == id).first()
    except OperationalError as e:
        logger.warning("query_counterbyid errorMsg= {} ".format(e))
        return None


def delete_counterbyid(id):
    """
    根据ID删除Counter实体
    :param id: Counter的ID
    """
    try:
        counter = Counters.query.get(id)
        if counter is None:
            return
        db.session.delete(counter)
        db.session.commit()
    except OperationalError as e:
        logger.warning("delete_counterbyid errorMsg= {} ".format(e))


def insert_counter(counter):
    """
    插入一个Counter实体
    :param counter: Counters实体
    """
    try:
        db.session.add(counter)
        db.session.commit()
    except OperationalError as e:
        logger.warning("insert_counter errorMsg= {} ".format(e))


def update_counterbyid(counter):
    """
    根据ID更新counter的值
    :param counter实体
    """
    try:
        counter = query_counterbyid(counter.id)
        if counter is None:
            return
        db.session.flush()
        db.session.commit()
    except OperationalError as e:
        logger.warning("update_counterbyid errorMsg= {} ".format(e))

# ----------- room---------
def query_roombyid(id):
    """
    根据ID查询Room实体
    :param id: Room的ID
    :return: Room实体
    """
    try:
        return Room.query.filter(Room.id == id).first()
    except OperationalError as e:
        logger.warning("query_roombyid errorMsg= {} ".format(e))
        return None


def query_using_roombyid(id):
    """
    根据ID查询使用中的Room实体
    :param id: Room的ID
    :return: Room实体
    """
    try:
        return Room.query.filter(Room.id == id, Room.status == 1).first()
    except OperationalError as e:
        logger.warning("query_using_roombyid errorMsg= {} ".format(e))
        return None

def query_using_room_by_usetime(time):
    """
    查询待关闭的房间
    :param id: Room的ID
    :return: Room实体
    """
    try:
        return Room.query.filter(Room.status == 1,Room.use_at<time).all()
    except OperationalError as e:
        logger.warning("query_using_room_by_usetime errorMsg= {} ".format(e))
        return None


def get_empty_room_and_update_status(myapp):
    """
    根据status 查询 Room 列表
    :param status: room 的 status
    :return: Room实体列表
    """
    try:
        room = Room.query.filter(Room.status == 0,Room.myapp == myapp).with_for_update().first()
        if room is not None:
            room.status = 1
            room.use_at = datetime.now()
            db.session.flush()
            db.session.commit()
        return room
    except OperationalError as e:
        logger.warning("get_empty_room_and_update_status errorMsg= {} ".format(e))
        return None

def insert_room(room):
    """
    插入一个room实体
    :param room: Room实体
    """
    try:
        db.session.add(room)
        db.session.commit()
    except OperationalError as e:
        logger.warning("insert_room errorMsg= {} ".format(e))
        # print("insert_room errorMsg= {} ".format(e))


def update_room_qr_byid(roomId, qr):
    """
    根据ID更新room的值
    :param room实体
    """
    try:
        room = query_roombyid(roomId)
        if room is None:
            return
        room.share_qr = qr
        db.session.flush()
        db.session.commit()
    except OperationalError as e:
        logger.warning("update_room_qr_byid errorMsg= {} ".format(e))


def updateUserLatestRoomId(userId, roomId):
    try:
        user = query_user_by_id(userId)
        if user is None:
            logger.warning("updateUserLatestRoomId 错误：id: {} 查询到到 user 为 None".format(userId))
            return
        user.latest_room_id = roomId
        db.session.flush()
        db.session.commit()
    except OperationalError as e:
        logger.warning("updateUserLatestRoomId errorMsg= {} ".format(e))
# -------------user-----

def insert_user(user):
    """
    插入一个user实体
    :param user: User实体
    """
    try:
        db.session.add(user)
        db.session.commit()
    except OperationalError as e:
        logger.warning("insert_user errorMsg= {} ".format(e))



def query_user_by_openid(openId,myapp):
    """
    根据openid查询User实体
    :param openId: User的openId
    :return: User实体
    """
    try:
        return User.query.filter(User.wx_openid == openId,User.myapp==myapp).first()
    except OperationalError as e:
        logger.warning("query_user_by_openid errorMsg= {} ".format(e))
        return None

def query_user_by_id(id):
    """
    根据openid查询User实体
    :param id: User的id
    :return: User实体
    """
    try:
        return User.query.filter(User.id == id).first()
    except OperationalError as e:
        logger.warning("query_user_by_id errorMsg= {} ".format(e))
        return None

def query_users_by_ids(ids):
    """
    根据ids查询User实体列表
    :param id: User的ids
    :return: User实体列表
    """
    try:
        return User.query.filter(User.id.in_(ids)).all()
    except OperationalError as e:
        logger.warning("query_users_by_ids errorMsg= {} ".format(e))
        return None

def update_user_by_id(userId, nickname,avatarUrl,avatarFileId):
    """
    根据ID更新user的值
    :param nickname 昵称
    :param avatarUrl 头像url
    :param avatarFileId 头像云存ID
    """
    try:
        user = query_user_by_id(userId)
        if user is None:
            return None
        user.nickname = nickname
        if avatarUrl is not None:
            user.avatar_url = avatarUrl
            user.avatar_fileid = avatarFileId
        db.session.flush()
        db.session.commit()
        return user
    except OperationalError as e:
        logger.warning("update_user_by_id errorMsg= {} ".format(e))
        return None


def add_user_to_room(uid, roomId):
    try:
        memberInfo = RoomMemberInfo.query.filter(RoomMemberInfo.user_id==uid,RoomMemberInfo.room_id==roomId).first()
        if memberInfo is None:
            room = query_roombyid(roomId)
            if room is None:
                logger.info("add_user_to_room 查询roomId:{} 为 None".format(roomId))
                return
            memberInfo = RoomMemberInfo(room_id=room.id,user_id=uid,room_name=room.name,status=1,settle_amount=0,time=datetime.now(),user_delete=0)
            db.session.add(memberInfo)
            db.session.commit()
        else:
            memberInfo.status=1
            db.session.flush()
            db.session.commit()
        # if not room.user_ids.__contains__(uid):
        #     room.user_ids.append(uid)
        #     flag_modified(room, "user_ids")
        #     db.session.flush()
        #     db.session.commit()
    except OperationalError as e:
        logger.warning("add_user_to_room errorMsg= {} ".format(e))


def autoReleaseRoom(roomId,userScores):
    try:
        roomMembers = RoomMemberInfo.query.filter(RoomMemberInfo.room_id == roomId, RoomMemberInfo.status == 1).all()
        if roomMembers is not None:
            for member in roomMembers:
                user = User.query.filter(User.id == member.user_id).first()
                if user is not None:
                    user.latest_room_id = 0
                member.status = 0
                member.settle_amount = userScores.get(f'{member.user_id}',0)
        room = Room.query.filter(Room.id == roomId).first()
        if room is not None:
            room.status = 2
            room.close_at = datetime.now()
        db.session.flush()
        db.session.commit()
    except OperationalError as e:
        logger.warning("autoReleaseRoom errorMsg= {} ".format(e))
        return None

# def rm_user_from_room(uid, roomId):
#     try:
#         room = query_using_roombyid(roomId)
#         if room is None:
#             logger.info("rm_user_from_room 查询roomId:{} 为 None".format(roomId))
#             return
#         if room.user_ids.__contains__(uid):
#             room.user_ids.remove(uid)
#             flag_modified(room, "user_ids")
#             db.session.flush()
#             db.session.commit()
#     except OperationalError as e:
#         logger.info("rm_user_from_room errorMsg= {} ".format(e))


# -------------room waste book-----
# 添加房间流水
def add_waste_to_room(roomWasteBook):
    try:
        db.session.add(roomWasteBook)
        db.session.commit()
    except OperationalError as e:
        logger.warning("add_waste_to_room errorMsg= {} ".format(e))
# 批量添加
def add_all_wastes_to_room(roomWasteList):
    try:
        db.session.add_all(roomWasteList)
        db.session.commit()
    except OperationalError as e:
        logger.warning("add_all_wastes_to_room errorMsg= {} ".format(e))

# 根据最后记录ID返回最新流水
def get_wastes_from_room_by_latestid(roomId:int,latestWasteId:int):
    try:
        return RoomWasteBook.query.filter(RoomWasteBook.room_id == roomId,RoomWasteBook.id>latestWasteId).order_by(RoomWasteBook.id).all()
    except OperationalError as e:
        logger.warning("get_wastes_from_room_by_latestid errorMsg= {} ".format(e))

# 查询房间的最后一条流水
def get_latest_wastes_from_room(roomId:int):
    try:
        return RoomWasteBook.query.filter(RoomWasteBook.room_id == roomId).order_by(RoomWasteBook.id.desc()).first()
    except OperationalError as e:
        logger.warning("get_latest_wastes_from_room errorMsg= {} ".format(e))

# 查询房间的支付流水
def get_outlay_wastes_from_room(roomId:int):
    try:
        return RoomWasteBook.query.filter(RoomWasteBook.room_id == roomId,RoomWasteBook.type==1).all()
    except OperationalError as e:
        logger.warning("get_outlay_wastes_from_room errorMsg= {} ".format(e))

# -------------room waste book- end----
# -------------room_member--start---
# 更新个人总得分
def rm_user_from_room_and_update_settle_score(userId:int,latestRoomId:int):
    try:
        # 创建参数化查询的查询字符串
        sql = text("SELECT COALESCE((SELECT sum(score) FROM room_waste_book WHERE TYPE=1 AND receive_user_id = :userId AND room_id = :roomId),0) - COALESCE((SELECT sum(score) FROM room_waste_book WHERE TYPE=1 AND outlay_user_id = :userId AND room_id=:roomId),0) AS score")
        # 执行参数化查询
        result = db.engine.execute(sql, roomId=latestRoomId, userId=userId)
        curScore = 0
        for r in result: # 只有一条数据 todo 去掉for
            curScore = r[0]
        # curScore = result['score']

        memberInfo = RoomMemberInfo.query.filter(RoomMemberInfo.user_id==userId,RoomMemberInfo.room_id==latestRoomId).first()
        if memberInfo is None:
            return
        memberInfo.settle_amount=curScore
        memberInfo.status=0
        db.session.flush()
        db.session.commit()
    except OperationalError as e:
        logger.warning("rm_user_from_room_and_update_settle_score errorMsg= {} ".format(e))


# 查询房间中的人员
def query_users_in_room(roomId, status=None):
    try:
        if status is None:
            return RoomMemberInfo.query.filter(RoomMemberInfo.room_id == roomId).all()
        return RoomMemberInfo.query.filter(RoomMemberInfo.room_id == roomId, RoomMemberInfo.status == status).all()
    except OperationalError as e:
        logger.warning("get_wastes_from_room_by_latestid errorMsg= {} ".format(e))

# 获取房间历史记录
def query_history_rooms_by_uid(userId):
    try:
        return RoomMemberInfo.query.filter(RoomMemberInfo.user_id == userId,RoomMemberInfo.status==0,RoomMemberInfo.user_delete != 1).order_by(RoomMemberInfo.time.desc()).all()
    except OperationalError as e:
        logger.warning("query_history_rooms_by_uid errorMsg= {} ".format(e))

def delete_history_room_by_uid_roomid(userId,roomId):
    try:
        roomMemberInfo = RoomMemberInfo.query.filter(RoomMemberInfo.user_id == userId, RoomMemberInfo.room_id == roomId).first()
        roomMemberInfo.user_delete = 1
        db.session.flush()
        db.session.commit()
        return True
    except OperationalError as e:
        logger.warning("query_history_rooms_by_uid errorMsg= {} ".format(e))
        return False



def query_room_member_by_roomids(roomIds, userId):
    try:
        return db.session.query(RoomMemberInfo.room_id, User.nickname).filter(User.id == RoomMemberInfo.user_id, RoomMemberInfo.room_id.in_(roomIds),
                                                                              RoomMemberInfo.user_id != userId).all()
    except OperationalError as e:
        logger.warning("query_room_member_by_roomids errorMsg= {} ".format(e))
        return None

def query_using_roomid_by_uid(uid):
    """
    根据uid查询使用中的Roomid
    :param id: Room的ID
    :return: Room实体
    """
    try:
        roomMember = RoomMemberInfo.query.filter(RoomMemberInfo.user_id == uid, RoomMemberInfo.status == 1).first()
        if roomMember is not None:
            return roomMember.room_id
        return None
    except OperationalError as e:
        logger.warning("query_using_roomid_by_uid errorMsg= {} ".format(e))
        return None

# 获取个人的成绩
def query_achievement_by_uid(userId):
    try:
        totalCount = RoomMemberInfo.query.filter(RoomMemberInfo.user_id == userId,RoomMemberInfo.user_delete != 1).count()
        successCount = RoomMemberInfo.query.filter(RoomMemberInfo.user_id == userId,RoomMemberInfo.user_delete != 1, RoomMemberInfo.settle_amount >= 0).count()
        return {"totalCount": totalCount, "successCount": successCount}
    except OperationalError as e:
        logger.warning("query_achievement_by_uid errorMsg= {} ".format(e))


# 查询游戏数据
def query_game_info(uid, wx_openid):
    try:
        if uid is not None:
            gameInfo = GameInfo.query.filter(GameInfo.uid == uid).first()
        else:
            gameInfo = GameInfo.query.filter(GameInfo.wx_openid == wx_openid).first()
            if gameInfo is None:
                gameInfo = GameInfo(wx_openid=wx_openid, v=int(time.time()))
                db.session.add(gameInfo)
                db.session.commit()
        return gameInfo
    except OperationalError as e:
        logger.warning("query_game_info errorMsg= {} ".format(e))


# 更新游戏数据
def update_game_info(uid, level, power):
    try:
        gameInfo = GameInfo.query.filter(GameInfo.uid == uid).first()
        if gameInfo is not None:
            gameInfo.v = int(time.time())
            gameInfo.power = power

            # 将JSON字符串转换为字典
            if gameInfo.level is not None:
                dict1 = json.loads(gameInfo.level)
                dict2 = level
                # 合并两个字典，dict2中的值会覆盖dict1中相同键的值
                dict1.update(dict2)
                gameInfo.level = json.dumps(dict1)
            else:
                gameInfo.level = json.dumps(level)
            logger.warning(gameInfo.level)
            db.session.flush()
            db.session.commit()

    except OperationalError as e:
        logger.warning("update_game_info errorMsg= {} ".format(e))
