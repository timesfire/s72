# 创建应用实例
import json
import sys

import gevent
import requests
from gevent import monkey
import threading

from gevent.queue import Empty

from wxcloudrun.WebsocketClient import WebsocketCWrap
# from wxcloudrun.views import background_task

monkey.patch_all()

from gevent.pywsgi import WSGIServer
from wxcloudrun import app, serverMsgQueue


def background_task():
    wsc = WebsocketCWrap()
    wsc.run()
    while True:
        try:
            item = serverMsgQueue.get(timeout=1)
            if item is not None:
                if not wsc.sendMsg(json.dumps(item)): # socket 发送失败，用http
                    requests.post(url="http://msg-notify-88593-7-1323709807.sh.run.tcloudbase.com/notifyWs",json=item)
        except Empty:
            pass
        gevent.sleep(0)

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
