# 创建应用实例
import sys

from wxcloudrun import app
# import eventlet
# from eventlet import wsgi

# 启动Flask Web服务
if __name__ == '__main__':
    # app.run()
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
    app.run(host=sys.argv[1], port=sys.argv[2],debug=False)

    # WSGIServer((sys.argv[1], sys.argv[2]), app).serve_forever()
    # wsgi.server(eventlet.listen((sys.argv[1], int(sys.argv[2]))), app)
    # socketio.run(app, host=sys.argv[1], port=sys.argv[2])
