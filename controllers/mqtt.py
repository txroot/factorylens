# controllers/mqtt.py

import json
from datetime import datetime
from config.database import db
from models.camera import Camera
from paho.mqtt.client import Client

# If you have a FunctionRequest model, import it here:
# from models.function_request import FunctionRequest

def execute_function(function: str, parameters: list) -> dict:
    """
    Stub for your actual function logic.
    Return a dict with at least 'status' and 'message' keys.
    """
    if function.lower() == "capture":
        # TODO: integrate with your camera SDK
        return {"status": "ok", "message": "Image captured successfully"}
    else:
        return {"status": "error", "message": f"Unknown function '{function}'"}

def on_connect(client: Client, userdata, flags, rc):
    print(f"MQTT connected with result code {rc}")
    client.subscribe("/camera/function/set")

def on_message(client: Client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        func       = payload.get("Function", "")
        params     = payload.get("Parameters", [])
        source     = payload.get("Source", "")
        ts_str     = payload.get("TimeStamp")
        ts         = datetime.fromisoformat(ts_str) if ts_str else datetime.utcnow()

        # 1. Execute the requested function
        result_info = execute_function(func, params)

        # 2. (Optional) persist to DB
        # from models.function_request import FunctionRequest
        # fr = FunctionRequest(
        #     source=source,
        #     function_name=func,
        #     parameters=json.dumps(params),
        #     timestamp=ts,
        #     result=result_info["message"]
        # )
        # db.session.add(fr); db.session.commit()

        # 3. Publish status back
        status = {
            "Request": payload,
            "Result": result_info
        }
        client.publish("/camera/function/status", json.dumps(status))

    except Exception as e:
        print("Error in MQTT message handler:", e)

def init_mqtt(client: Client):
    """
    Call this during your app startup (e.g. from utils/mqtt_client.py).
    """
    client.on_connect = on_connect
    client.on_message = on_message
    # client.connect(...) and loop_start() remain in your mqtt utility
