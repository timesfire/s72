import websocket

from wxcloudrun import app


class WebsocketCWrap:
    def __init__(self):
        websocket.enableTrace(False)
        self.ws = websocket.WebSocketApp("ws://fwajxmqp.msg-notify.2x8l7gg4.0lvje04z.com/notifyWsx",
                                         on_open=self.on_open,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.isOpen = False

    def on_message(self, ws, message):
        app.logger.warn(message)

    def on_error(self, ws, error):
        app.logger.warn(error)
        self.isOpen = False

    def on_close(self, ws, close_status_code, close_msg):
        app.logger.warn("### closed ###")
        self.isOpen = False

    def on_open(self, ws):
        app.logger.warn("Opened connection")
        print("Opened connection")
        self.isOpen = True

    def run(self):
        self.ws.run_forever(reconnect=10)

    def sendMsg(self, msg):
        if self.isOpen:
            self.ws.send(msg)
            return True
        return False


if __name__ == "__main__":
    WebsocketCWrap().run()
