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
    name = db.Column(db.Character)
    status = db.Column(db.Integer, default=1)
    created_at = db.Column('created_at', db.TIMESTAMP, nullable=False, default=datetime.now())
