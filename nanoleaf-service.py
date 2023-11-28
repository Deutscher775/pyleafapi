import pathlib
import time
import nanoleafapi
import nanoleaf_config
import fastapi
import uvicorn

api = fastapi.FastAPI()

nl = nanoleafapi.Nanoleaf(ip=nanoleaf_config.IP, auth_token=nanoleaf_config.TOKEN, print_errors=True)
nl_panels = nanoleafapi.NanoleafDigitalTwin(nl)


@api.post("/power")
def power(state: bool = None):
    if state is None:
        pass
    elif state is True:
        nl.power_on()
    elif state is False:
        nl.power_off()


@api.post("/panels/sync")
def sync_panel_configs():
    return nl_panels.sync()

@api.get("/layout")
def return_layout():
    return fastapi.responses.Response(content=f"{pathlib.Path(__file__).parent.parent.resolve()}/nanoleaf-service/panel-layout.png")

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
                    changed[panel] = {"rgb": {"r": int(rgb_val[0]), "g": int(rgb_val[1]), "b": int(rgb_val[2])}, "set": set}
                    return changed
            else:
                return fastapi.responses.Response(status_code=422, content="ValueError: 'rbg' must include all rgb values. (r, g, b)")
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
                return fastapi.responses.Response(status_code=422, content="ValueError: 'rbg' must include all rgb values. (r, g, b)")



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

effect = nl.get_current_effect()
nl.set_effect("API Start Animation")
time.sleep(3)
nl.set_effect(effect)

uvicorn.run(api, host="localhost", port=9931)