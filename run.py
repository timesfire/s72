# 创建应用实例
import sys

from wxcloudrun import app, socketio

# 启动Flask Web服务
if __name__ == '__main__':
    # socketio.run(app)
    socketio.run(app, host=sys.argv[1], port=sys.argv[2])
    # app.run(host=sys.argv[1], port=sys.argv[2])
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
