import fastapi
import uvicorn

api = fastapi.FastAPI()

class Plugin():
    def __init__(self, handler):
        self.handler = handler
        self.config = {
            "port": 9933,
        }

    def run(self):
    
        @api.get("/togglestate")
        def togglestate():
            current_state = self.handler.nanoleaf.get_power()
            if current_state:
                self.handler.nanoleaf.power_off()
                return fastapi.responses.JSONResponse({"state": False}, status_code=200)
            else:
                self.handler.nanoleaf.power_on()
                return fastapi.responses.JSONResponse({"state": True}, status_code=200)
    
        uvicorn.run(api, host=self.handler.host, port=self.config["port"])
