from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import pymysql
from gevent.queue import Queue

import config
from flask_sock import Sock
# 因MySQLDB不支持Python3，使用pymysql扩展库代替MySQLDB库
pymysql.install_as_MySQLdb()

# 初始化web应用
app = Flask(__name__, instance_relative_config=True)
app.config['DEBUG'] = config.DEBUG
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
sock = Sock(app)

# app.config['SECRET_KEY'] = 'secret!'
# socketio = SocketIO(app)

# 设定数据库链接
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://{}:{}@{}/flask_demo?charset=utf8mb4'.format(config.username, config.password,
                                                                            config.db_address)
app.config['SQLALCHEMY_POOL_SIZE'] = 50
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 10
app.config['SQLALCHEMY_POOL_RECYCLE'] = 4800



# 初始化DB操作对象
db = SQLAlchemy(app)
serverMsgQueue = Queue()


# 加载控制器
from wxcloudrun import views

# 加载配置
app.config.from_object('config')
