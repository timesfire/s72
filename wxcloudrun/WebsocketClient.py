import websocket


class WebsocketClient:
    def __init__(self):
        self.ws = websocket.WebSocketApp("ws://echo.websocket.org/",
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
    def on_message(ws, message):
        print(f"Received message: {message}")

    def on_error(ws, error):
        print(f"Error: {error}")

    def on_close(ws):
        print("Connection closed")

    def on_open(ws):
        print("Connection opened")
        ws.send("Hello, WebSocket!")

    def run(self):
        self.ws.run_forever()


if __name__ == "__main__":
    websocket.enableTrace(True)
    WebsocketClient().run()
