# 创建应用实例
import sys
from gevent import monkey
import threading

monkey.patch_all()

from gevent.pywsgi import WSGIServer
from wxcloudrun import app
from wxcloudrun.views import background_task

# 启动Flask Web服务
if __name__ == '__main__':
    # app.run()
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
    # app.run(host=sys.argv[1], port=sys.argv[2])
    thread = threading.Thread(target=background_task)
    thread.daemon = True  # 设置为守护线程，以便 Flask 应用退出时自动结束
    thread.start()
    WSGIServer((sys.argv[1], int(sys.argv[2])), app).serve_forever()
    # wsgi.server(eventlet.listen((sys.argv[1], int(sys.argv[2]))), app)
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
