from datetime import datetime
import random

from flask import render_template, request
from run import app
from wxcloudrun.dao import delete_counterbyid, query_counterbyid, insert_counter, update_counterbyid, insert_room
from wxcloudrun.model import Counters, Room
from wxcloudrun.response import make_succ_empty_response, make_succ_response, make_err_response

words = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

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


@app.route('/api/createRoom', methods=['POST'])
def create_room():
    """
    :return: 房间信息xx
    """
    room = Room(name=randomRoomName(), status=1, created_at=datetime.now())
    insert_room(room)
    return make_succ_response(room.id)


def randomRoomName():
    terms = ''
    for _ in range(3):
        terms = terms + str(random.sample(words, 1))
    return terms
