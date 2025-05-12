
# 📷 Reolink RLC-810A RTSP and Snapshot URLs

## 🎥 RTSP Stream (Live Video)

### 🔹 Main Stream (High Quality)
```
rtsp://admin:reolink@10.20.1.157:554/h264Preview_01_main
```

### 🔸 Sub Stream (Lower Bandwidth)
```
rtsp://admin:reolink@10.20.1.157:554/h264Preview_01_sub
```

> Replace `h264` with `h265` if your camera is configured for H.265:
> - `h265Preview_01_main`
> - `h265Preview_01_sub`

---

## 🖼️ Snapshot (Still Image)

### 📸 Capture JPEG Snapshot
```
http://10.20.1.157/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=abc123&user=admin&password=reolink
```

### 📐 Optional: With Resolution (if supported)
```
http://10.20.1.157/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=abc123&user=admin&password=reolink&width=1920&height=1080
```

---

## 🔐 Notes

- Replace `admin` and `reolink` with your actual username and password.
- You can test these links in VLC or a browser (for snapshots).
- Use `https://...` instead of `http://` if HTTPS is enabled on your camera.
