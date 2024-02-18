# 创建应用实例
import sys
from gevent import monkey
monkey.patch_all()
from gevent.pywsgi import WSGIServer
from wxcloudrun import app


# 启动Flask Web服务
if __name__ == '__main__':
    # app.run()
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
    # app.run(host=sys.argv[1], port=sys.argv[2])
    WSGIServer((sys.argv[1], int(sys.argv[2])), app).serve_forever()
    # wsgi.server(eventlet.listen((sys.argv[1], int(sys.argv[2]))), app)
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
