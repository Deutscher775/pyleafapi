import datetime
import time
import nanoleafapi
import requests
import nanoleaf_config
import fastapi
import uvicorn
import os
import inspect
from nanoleafapi import discovery
import socket
from fastapi.middleware.cors import CORSMiddleware
from plugins import *
import importlib
import threading


def get_local_device_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    return local_ip

api = fastapi.FastAPI()

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

nl = nanoleafapi.Nanoleaf(ip=nanoleaf_config.IP, auth_token=nanoleaf_config.TOKEN, print_errors=True)
nl.create_auth_token()
nl_panels = nanoleafapi.NanoleafDigitalTwin(nl)

loaded_plugins = {}


def log(content: str):
    curframe = inspect.currentframe()
    callframe = inspect.getouterframes(curframe, 2)
    print(f"[{datetime.datetime.time(datetime.datetime.now())}] - [{callframe.filename}]: {content}")


class PluginHandler:
    def __init__(self):
        self.plugins = []
        self.host = get_local_device_ip()
        self.port = 9931
        self.nanoleaf = nl

    @staticmethod
    def log(content: str):
        print(f"[{datetime.datetime.time(datetime.datetime.now()).replace(microsecond=0)}] - [{inspect.stack()[1].filename.split('/')[-1].replace('.py', '')}]: {content}")

    def initialize_plugins(self):
        plugin_dir = os.path.join(os.path.dirname(__file__), "plugins")
        for filename in os.listdir(plugin_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = f"plugins.{filename[:-3]}"
                thread = threading.Thread(target=self.load_plugin, args=(module_name,))
                thread.daemon = True
                thread.start()
                loaded_plugins[filename.split(".")[-2]] = {
                    "module": module_name,
                    "loaded": True,
                }

    def load_plugin(self, module_name):
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "Plugin"):
                plugin_class = getattr(module, "Plugin")
                plugin_instance = plugin_class(self)
                self.plugins.append(plugin_instance)
                PluginHandler.log(f"Initialized plugin: {module_name}")
                if hasattr(plugin_instance, "run"):
                    if plugin_instance.config.get("port"):
                        loaded_plugins[f"{module_name.split('.')[1]}"]["port"] = plugin_instance.config["port"]
                    plugin_instance.run()
            else:
                PluginHandler.log(f"No `Plugin` class found in {module_name}")
        except Exception as e:
            PluginHandler.log(f"Failed to load {module_name}: {e}")


@api.post("/power")
def power(state: bool = None):
    if state is None:
        pass
    elif state is True:
        nl.power_on()
        return fastapi.responses.JSONResponse({"state": True}, status_code=200)
    elif state is False:
        nl.power_off()
        return fastapi.responses.JSONResponse({"state": False}, status_code=200)


@api.get("/plugins/loaded")
def get_plugins():
    plugins = loaded_plugins
    print(plugins)
    return plugins

@api.get("/p/{plugin}/{path:path}")
def plugin_path(plugin: str, path: str):
    if plugin in loaded_plugins:
        module_name = loaded_plugins[plugin]["module"]
        if "port" in loaded_plugins[plugin]:
            port = loaded_plugins[plugin]["port"]
            url = f"http://{get_local_device_ip()}:{port}/{path}"
            response = requests.get(url)
            return fastapi.responses.JSONResponse(content=response.json(), status_code=response.status_code)
        else:
            module = importlib.import_module(module_name)
            if hasattr(module, "Plugin"):
                plugin_class = getattr(module, "Plugin")
                plugin_instance = plugin_class(handler)
                if hasattr(plugin_instance, "handle_path"):
                    return plugin_instance.handle_path(path)
    return fastapi.responses.JSONResponse({"error": "Plugin or path not found"}, status_code=404)


@api.post("/panels/sync")
def sync_panel_configs():
    return nl_panels.sync()


@api.get("/layout")
def return_layout():
    # return fastapi.responses.Response(content=f"{pathlib.Path(__file__).parent.parent.resolve()}/nanoleaf-service/panel-layout.png")
    return nl.get_layout()


@api.post("/set")
def set(rgb: str = None, brightness: int = 0, effect: str = None, panel: int = None, all: bool = None):
    if panel:
        changed = {}
        if rgb is None:
            return fastapi.responses.Response(status_code=422,
                                              content="ValueError: 'rbg' must include all rgb values. (255, 255, 255)")
        else:
            rgb_val = rgb.split(",")
            if len(rgb_val) == 3:
                if all is True:
                    nl_panels.set_all_colors(rgb=(int(rgb_val[0]), int(rgb_val[1]), int(rgb_val[2])))
                else:
                    set = nl_panels.set_color(panel_id=panel, rgb=(int(rgb_val[0]), int(rgb_val[1]), int(rgb_val[2])))
                    changed[panel] = {"rgb": {"r": int(rgb_val[0]), "g": int(rgb_val[1]), "b": int(rgb_val[2])},
                                      "set": set}
                    return changed
            else:
                return fastapi.responses.Response(status_code=422,
                                                  content="ValueError: 'rbg' must include all rgb values. (r, g, b)")
    else:
        if brightness != 0:
            nl.set_brightness(brightness)
            return True
        if rgb is None and effect is not None:
            nl.set_effect(effect)
            return True
        elif rgb is None and effect is None:
            return fastapi.responses.Response(status_code=422,
                                              content="ValueError: 'rbg' must include all rgb values. (r, g, b)")
        else:
            rgb_val = rgb.split(",")
            if len(rgb_val) == 3:
                nl.set_color((int(rgb_val[0]), int(rgb_val[1]), int(rgb_val[2])))
                return True
            else:
                return fastapi.responses.Response(status_code=422,
                                                  content="ValueError: 'rbg' must include all rgb values. (r, g, b)")


@api.get("/get")
def get():
    data_get = nl.get_info()
    data_get.pop("serialNo")
    data_get.pop("panelLayout")
    data_get.pop("name")
    data_get.pop("model")
    data_get.pop("manufacturer")
    data_get["effects"]["current"] = data_get["effects"].pop("select")
    data_get.pop("firmwareUpgrade")
    data_get.pop("firmwareVersion")
    data_get.pop("hardwareVersion")
    data_get.pop("schedules")
    data_get.pop("qkihnokomhartlnp")
    data_get.pop("discovery")
    return data_get


@api.get("/get/effect")
def get_effect(effect: str):
    r = requests.put(f"http://{nanoleaf_config.IP}:16021/api/v1/{nanoleaf_config.TOKEN}/effects",
                     json={"write": {"command": "request", "animName": effect}})
    return r.json()


@api.get("/get/effect/colortheme")
def get_effect_colortheme():
    hue_list = {}
    try:
        effectslist = nl.get_info()["effects"]["effectsList"]
    except:
        time.sleep(0.5)
        effectslist = nl.get_info()["effects"]["effectsList"]
    for effect in effectslist:
        r = requests.put(f"http://{nanoleaf_config.IP}:16021/api/v1/{nanoleaf_config.TOKEN}/effects",
                         json={"write": {"command": "request", "animName": effect}})
        palette = r.json()["palette"]
        hue_list[effect] = [palette[0], palette[-1]]
    return hue_list


def start_anim():
    effect = nl.get_current_effect()
    nl.set_effect("API Start Animation")
    time.sleep(3)
    nl.set_effect(effect)

#start_anim()


if __name__ == "__main__":
    handler = PluginHandler()
    handler.initialize_plugins()
    print(get_local_device_ip())
    uvicorn.run(api, host=get_local_device_ip(), port=9931)
