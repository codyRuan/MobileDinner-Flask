from app import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=True)  # Make username nullable
    email = db.Column(db.String(120), unique=True, nullable=True)  # Make email nullable
    password_hash = db.Column(db.String(128), nullable=True)  # Make password_hash nullable
    line_user_id = db.Column(db.String(64), unique=True, nullable=False)  # LINE user ID
    display_name = db.Column(db.String(64), nullable=False)  # LINE display name
    picture_url = db.Column(db.String(256), nullable=True)  # LINE profile picture URL
    vendors = db.relationship('Vendor', backref='owner', lazy='dynamic')

class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), index=True, unique=True)
    link = db.Column(db.String(120))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 添加外鍵關係

    def __repr__(self):
        return f'<Vendor {self.name}>'

class VendorSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String, nullable=False)
    vendor = db.relationship('Vendor', backref=db.backref('schedules', lazy=True))

    def __repr__(self):
        return f'<VendorSchedule {self.vendor_id} from {self.start_date} to {self.end_date}>'

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'))
