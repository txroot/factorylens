# models/camera_stream.py

from extensions import db
from datetime import datetime
from sqlalchemy.orm import relationship, backref

class CameraStream(db.Model):
    __tablename__ = 'camera_streams'

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.Integer, db.ForeignKey('cameras.id'), nullable=False)

    # Link to parent camera
    camera_id = db.Column(db.Integer, db.ForeignKey('cameras.id'), nullable=False)
    camera = relationship(
        'Camera',
        backref=backref('streams', foreign_keys=[camera_id]),
        foreign_keys=[camera_id]
    )

    # Type of stream channel
    stream_type = db.Column(
        db.Enum('main', 'sub', 'fluent', 'custom', name='camera_stream_type'),
        nullable=False,
        comment="Type of stream channel"
    )

    # Prefix and suffix for building stream URLs
    url_prefix = db.Column(db.String(255), comment="Path prefix for stream URL, e.g. /h264Preview_01_")
    stream_suffix = db.Column(db.String(255), nullable=True, comment="Suffix for stream path, e.g. main, sub")

    # Optional full URL override
    full_url = db.Column(db.String(255), nullable=True, comment="Full RTSP/HTTP stream URL (overrides prefix+suffix)")

    # Encoding and performance
    resolution_w = db.Column(db.Integer)
    resolution_h = db.Column(db.Integer)
    fps = db.Column(db.Integer)
    codec = db.Column(db.String(50), comment="e.g. H.264, H.265, MJPEG")
    bitrate_kbps = db.Column(db.Integer)
    bitrate_type = db.Column(db.String(50), comment="CBR, VBR")

    # Other metadata
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_full_url(self, include_auth=True):
        """
        Construct the full RTSP/HTTP stream URL using camera credentials and path parts.

        - If `full_url` is set, it will be returned as-is.
        - Otherwise, it constructs the URL using prefix + suffix.

        :param include_auth: Whether to include username/password in the URL
        :return: Complete stream URL as a string
        """
        if self.full_url:
            return self.full_url

        # Basic path assembly
        path = f"{(self.url_prefix or '').rstrip('/')}/{(self.stream_suffix or '').lstrip('/')}"

        # Add auth if requested and available
        if include_auth and self.camera.username:
            auth = f"{self.camera.username}:{self.camera.password}@"
        else:
            auth = ""

        return f"rtsp://{auth}{self.camera.address}:{self.camera.port}{path}"

    def __repr__(self):
        return f"<Stream {self.stream_type} for Camera ID {self.camera_id}>"
