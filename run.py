# 创建应用实例
from gevent import monkey
monkey.patch_all()
import sys
import json
import gevent
import requests
import threading
from gevent.queue import Empty
from wxcloudrun.WebsocketClient import WebsocketCWrap
from gevent.pywsgi import WSGIServer
from wxcloudrun import app, serverMsgQueue

wsc = WebsocketCWrap()

def runWebsocket():
    wsc.run()

def background_task():
    while True:
        try:
            app.logger.warn("运行中")
            item = serverMsgQueue.get(timeout=1)
            if item is not None:
                app.logger.warn(f'开始发送消息:{item}')
                if not wsc.sendMsg(json.dumps(item)): # socket 发送失败，用http
                    app.logger.warn("发送失败")
                    requests.post(url="http://msg-notify-88593-7-1323709807.sh.run.tcloudbase.com/notifyWs",json=item)
        except Empty:
            pass
        gevent.sleep(0)

# 启动Flask Web服务
if __name__ == '__main__':
    # app.run()
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
    # app.run(host=sys.argv[1], port=sys.argv[2])

    runConnThread = threading.Thread(target=runWebsocket)
    runConnThread.daemon = True  # 设置为守护线
    runConnThread.start()

    thread = threading.Thread(target=background_task)
    thread.daemon = True  # 设置为守护线程，以便 Flask 应用退出时自动结束
    thread.start()

    WSGIServer((sys.argv[1], int(sys.argv[2])), app).serve_forever()
    # wsgi.server(eventlet.listen((sys.argv[1], int(sys.argv[2]))), app)
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
