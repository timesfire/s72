from flask import Flask
import config
from flask_sock import Sock


# 初始化web应用
app = Flask(__name__, instance_relative_config=True)
app.config['DEBUG'] = config.DEBUG
app.config['SOCK_SERVER_OPTIONS'] = {'ping_interval': 25}
sock = Sock(app)


# 加载控制器
from wxcloudrun import views

# 加载配置
app.config.from_object('config')
