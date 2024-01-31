# 创建应用实例
import sys

from wxcloudrun import app

# 启动Flask Web服务
if __name__ == '__main__':
    # app.run()
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
    app.run(host=sys.argv[1], port=sys.argv[2],debug=False)
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
