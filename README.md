# Factory Lens

**Factory Lens** is a modular event-driven automation platform developed by **Microlumin Lda**. It integrates cameras, IoT modules, loggers, and intelligent processors into a unified system for monitoring, logging, and executing automated actions based on device events.

---

## 🚀 Features

- 🧠 **Event-Driven Logic Flows** with conditional actions and timers  
- 🕹️ **Unified API** for all device types (camera, IoT, logger, etc.)  
- 📦 **Modular Device Management** and provisioning  
- 🗂️ **Centralized Logging** with filtering and notification triggers  
- 🔄 **Parameter Handling** for custom device actions  
- 🧾 **Backup & Archival System** for logs and configurations  
- 👥 **User and Role Management** (RBAC)

---

## 🧠 Key Concept: All Are Devices

Just like Linux treats everything as a file, **Factory Lens** treats everything as a **device**.

Whether it’s a:

- 📷 **Camera**
- ✉️ **Messenger**
- 📦 **Module**
- 🌐 **IoT Device**
- 📝 **Logger**
- 💾 **Storage Unit**
- 🧠 **AI Processor**

...they all conform to a unified interface and share a common structure.

This design simplifies integration, flow building, and system management by making all components interchangeable in automation workflows.

---

## 🔧 Supported Device Types

- **Camera** (screenshots, streaming)
- **Messenger** (email, messaging)
- **Module** (custom processing units)
- **IoT Device** (e.g. sensors, actuators)
- **Logger** (system or device logs)
- **Storage Unit**
- **AI Processor** (computer vision, log analysis)

> All devices are treated uniformly via a shared API interface.

---

## 🧩 Flow Example

```mermaid
flowchart TD
    A[Device Input Event (Impulse)] --> B[Save to File]
    B --> C{Check Condition}
    C -->|Yes| D[Device Output - ON]
    C -->|No| E[Log Event]
    D --> F[Wait 2 seconds]
    F --> G[Device Output - OFF]
    G --> H[Log Shutdown]
```

---

## 📥 Inputs / Outputs

- **Inputs** and **outputs** use JSON:
  ```json
  {
    "inputs": { "event": "impulse", "device": "relay01" },
    "outputs": [
      { "device": "camera01", "action": "screenshot" },
      { "device": "relay02", "action": "turnOn", "timer": 5 }
    ]
  }
  ```

- Supported parameters:
  - `timeout`
  - `fire-and-forget`
  - `value`, `state`, `time`

---

## 🗃️ Database Schema

| Collection     | Description                | Key Fields          |
|----------------|----------------------------|---------------------|
| `camera`       | Camera metadata            | `device_id`         |
| `module`       | Custom modules             | `device_id`         |
| `iot_device`   | Sensor/actuator info       | `device_id`         |
| `messenger`    | Notification channels      | `device_id`         |
| `logger`       | Logging configuration      | `device_id`         |
| `storage_unit` | File/blob storage units    | `device_id`         |
| `ai_processor` | Vision/log analysis tools  | `device_id`         |
| `user`         | User accounts              | `user_id`, `role`   |
| `role`         | Role definitions           | `permissions`       |

---

## 🛠 System Services

- 🔁 **Automated DB Backups**
- 📤 **Send Device Parameters** (e.g. to Shelly units)
- 🧾 **Export & Archive Logs**
- 🔧 **Device Provisioning**
- 👤 **User & Role Management**

---

## 📦 Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/microlumin/factory-lens.git
   cd factory-lens
   ```
2. Install dependencies and configure `.env`
3. Start the platform:
   ```bash
   docker-compose up
   ```

---

## 📄 License

This project is licensed under the MIT License.

---

## 👨‍💻 Author

**André Rocha**  
Microlumin Lda  
📧 dev@microlumin.pt

---

## 🤝 Contributions

Feel free to open issues or submit pull requests for suggestions, improvements, or bug fixes.

---