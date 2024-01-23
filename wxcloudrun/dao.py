import json
import logging

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.attributes import flag_modified

from wxcloudrun import db
from wxcloudrun.model import Counters, Room, User,RoomWasteBook

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
        logger.info("query_counterbyid errorMsg= {} ".format(e))
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
        logger.info("delete_counterbyid errorMsg= {} ".format(e))


def insert_counter(counter):
    """
    插入一个Counter实体
    :param counter: Counters实体
    """
    try:
        db.session.add(counter)
        db.session.commit()
    except OperationalError as e:
        logger.info("insert_counter errorMsg= {} ".format(e))


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
        logger.info("update_counterbyid errorMsg= {} ".format(e))

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
        logger.info("query_roombyid errorMsg= {} ".format(e))
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
        logger.info("query_roombyid errorMsg= {} ".format(e))
        return None


def get_empty_room_and_update_status():
    """
    根据status 查询 Room 列表
    :param status: room 的 status
    :return: Room实体列表
    """
    try:
        room = Room.query.filter(Room.status == 0).with_for_update().first()
        if room is not None:
            room.status = 1
            db.session.flush()
            db.session.commit()
        return room
    except OperationalError as e:
        logger.info("get_empty_room errorMsg= {} ".format(e))
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
        logger.info("insert_room errorMsg= {} ".format(e))
        print("insert_room errorMsg= {} ".format(e))


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
        logger.info("update_counterbyid errorMsg= {} ".format(e))


def updateUserLatestRoomId(userId, roomId):
    try:
        user = query_user_by_id(userId)
        if user is None:
            logger.info("updateUserLatestRoomId 错误：id: {} 查询到到 user 为 None".format(userId))
            return
        user.latest_room_id = roomId
        db.session.flush()
        db.session.commit()
    except OperationalError as e:
        logger.info("insert_user errorMsg= {} ".format(e))



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
        logger.info("insert_user errorMsg= {} ".format(e))



def query_user_by_openid(openId):
    """
    根据openid查询User实体
    :param openId: User的openId
    :return: User实体
    """
    try:
        return User.query.filter(User.wx_openid == openId).first()
    except OperationalError as e:
        logger.info("query_user_by_openid errorMsg= {} ".format(e))
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
        logger.info("query_user_by_id errorMsg= {} ".format(e))
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
        logger.info("query_users_by_ids errorMsg= {} ".format(e))
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
            return
        user.nickname = nickname
        user.avatar_url = avatarUrl
        user.avatar_fileid = avatarFileId
        db.session.flush()
        db.session.commit()
    except OperationalError as e:
        logger.info("update_user_by_id errorMsg= {} ".format(e))


def add_user_to_room(uid, roomId):
    try:
        room = query_roombyid(roomId)
        if room is None:
            logger.info("add_user_to_room 查询roomId:{} 为 None".format(roomId))
            return
        if not room.user_ids.__contains__(uid):
            room.user_ids.append(uid)
            flag_modified(room, "user_ids")
            db.session.flush()
            db.session.commit()
    except OperationalError as e:
        logger.info("add_user_to_room errorMsg= {} ".format(e))


def rm_user_form_room(uid, roomId):
    try:
        room = query_using_roombyid(roomId)
        if room is None:
            logger.info("add_user_to_room 查询roomId:{} 为 None".format(roomId))
            return
        if room.user_ids.__contains__(uid):
            room.user_ids.remove(uid)
            flag_modified(room, "user_ids")
            db.session.flush()
            db.session.commit()
    except OperationalError as e:
        logger.info("rm_user_form_room errorMsg= {} ".format(e))


# -------------room waste book-----
# 添加房间流水
def add_waste_to_room(roomWasteBook):
    try:
        db.session.add(roomWasteBook)
        db.session.commit()
    except OperationalError as e:
        logger.info("add_waste_to_room errorMsg= {} ".format(e))
# 批量添加
def add_all_wastes_to_room(roomWasteList):
    try:
        db.session.add_all(roomWasteList)
        db.session.commit()
    except OperationalError as e:
        logger.info("add_all_wastes_to_room errorMsg= {} ".format(e))

# 根据最后记录ID返回最新流水
def get_wastes_from_room_by_latestid(roomId:int,latestWasteId:int):
    try:
        return RoomWasteBook.query.filter(RoomWasteBook.room_id == roomId,RoomWasteBook.id>latestWasteId).order_by(RoomWasteBook.id).all()
    except OperationalError as e:
        logger.info("get_wastes_from_room_by_latestid errorMsg= {} ".format(e))