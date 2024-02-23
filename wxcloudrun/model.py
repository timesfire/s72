from datetime import datetime


from wxcloudrun import db


# 计数表
class Counters(db.Model):
    # 设置结构体表格名称
    __tablename__ = 'Counters'

    # 设定结构体对应表格的字段
    id = db.Column(db.Integer, primary_key=True)
    count = db.Column(db.Integer, default=1)
    created_at = db.Column('createdAt', db.TIMESTAMP, nullable=False, default=datetime.now())
    updated_at = db.Column('updatedAt', db.TIMESTAMP, nullable=False, default=datetime.now())


class Room(db.Model):
    # 设置结构体表格名称
    __tablename__ = 'room'

    # 设定结构体对应表格的字段
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    status = db.Column(db.Integer, default=0) #房间状态 0 未使用，1使用中，2已使用
    share_qr = db.Column(db.String(255))
    created_at = db.Column('created_at', db.TIMESTAMP, nullable=False, default=datetime.now())
    use_at = db.Column('use_at', db.TIMESTAMP, nullable=True)
    close_at = db.Column('close_at', db.TIMESTAMP, nullable=True)
    user_ids = db.Column("user_ids", db.JSON)
    myapp = db.Column(db.String(10))



class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(100))
    wx_unionid = db.Column(db.String(100))
    wx_openid = db.Column(db.String(100))
    wx_session_key = db.Column(db.String(100))
    avatar_url = db.Column(db.String(200))
    avatar_fileid = db.Column(db.String(200))
    latest_room_id = db.Column("latest_room_id", db.Integer)
    myapp = db.Column(db.String(10))
    time = db.Column('time', db.TIMESTAMP, nullable=False, default=datetime.now())

class RoomWasteBook(db.Model):
    # 房间流水表
    __tablename__ = 'room_waste_book'

    # 设定结构体对应表格的字段
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer)
    outlay_user_id = db.Column(db.Integer)
    receive_user_id = db.Column(db.Integer)
    score = db.Column(db.Float)
    type = db.Column(db.Integer) # 流水类型 1支付 2进入 3退出 4结算 5修改个人信息 6 茶水设置
    user_id = db.Column(db.Integer)
    user_nickname = db.Column(db.String(100))
    user_avatar_url = db.Column(db.String(200))
    msg = db.Column(db.String(50))
    settle_info = db.Column(db.String(500))
    time = db.Column('time', db.TIMESTAMP, nullable=False, default=datetime.now())
    tea_ratio = db.Column(db.Integer)  # 默认值 0
    tea_limit = db.Column(db.Integer)  # 茶水金额上限,-1无限制



class RoomMemberInfo(db.Model):
    # 房间人员各种信息
    __tablename__ = 'room_member'

    # 设定结构体对应表格的字段
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    room_id = db.Column(db.Integer)
    room_name= db.Column(db.String(20))
    settle_amount = db.Column(db.Float)
    status = db.Column(db.Integer)   # 1进入，0退出
    time = db.Column('time', db.TIMESTAMP, nullable=False, default=datetime.now())
