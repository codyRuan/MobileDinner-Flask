from flask import render_template, flash, redirect, url_for, request, jsonify, Flask
import requests
import os
from datetime import datetime, time
from dotenv import load_dotenv

from app import app, db, oauth
from app.models import User, Vendor, VendorSchedule, Favorite
from flask_login import current_user, login_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

load_dotenv()
CORS(app)

@app.route('/')
@app.route('/index')
def index():
    if current_user.is_authenticated:
        vendors = Vendor.query.all()
        return render_template('index.html', title='Home', vendors=vendors)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html', title='Sign In')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('authorize_google', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/login/facebook')
def login_facebook():
    redirect_uri = url_for('authorize_facebook', _external=True)
    return oauth.facebook.authorize_redirect(redirect_uri)

@app.route('/authorize/google')
def authorize_google():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.parse_id_token(token)
    user = User.query.filter_by(email=user_info['email']).first()
    if not user:
        user = User(username=user_info['name'], email=user_info['email'])
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return redirect(url_for('index'))

@app.route('/authorize/facebook')
def authorize_facebook():
    token = oauth.facebook.authorize_access_token()
    user_info = oauth.facebook.get('me?fields=id,name,email').json()
    user = User.query.filter_by(email=user_info['email']).first()
    if not user:
        user = User(username=user_info['name'], email=user_info['email'])
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return redirect(url_for('index'))

@app.route('/api/add_vendor', methods=['POST'])
def create_vendor():
    data = request.json
    name = data.get('name')
    link = data.get('link')
    user_email = data.get('user_email')
    print(data)

    if not name:
        return jsonify({'message': 'Missing Name'}), 400

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Check if vendor with the same name already exists for the user
    existing_vendor = Vendor.query.filter_by(name=name, user_id=user.id).first()

    if existing_vendor:
        new_vendor = existing_vendor
        new_vendor.link = link  # Update the link if necessary
    else:
        new_vendor = Vendor(name=name, link=link, user_id=user.id)
        db.session.add(new_vendor)
        db.session.commit()  # Commit to get the vendor ID

    start_date_time = data.get('start_date')
    end_date_time = data.get('end_date')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    address = data.get('address')

    if start_date_time and end_date_time and latitude is not None and longitude is not None and address:
        start_datetime = datetime.fromisoformat(start_date_time[:-1])  # Remove 'Z' and convert to datetime
        end_datetime = datetime.fromisoformat(end_date_time[:-1])  # Remove 'Z' and convert to datetime
        if end_datetime <= start_datetime:
            return jsonify({'message': 'End date must be after start date'}), 400
        
        # Remove seconds from time components
        start_time = time(start_datetime.hour, start_datetime.minute, 0)
        end_time = time(end_datetime.hour, end_datetime.minute, 0)

        new_schedule = VendorSchedule(
            vendor_id=new_vendor.id, 
            start_date=start_datetime.date(), 
            start_time=start_time, 
            end_date=end_datetime.date(), 
            end_time=end_time, 
            latitude=latitude, 
            longitude=longitude,
            address=address
        )
        db.session.add(new_schedule)
    else:
        return jsonify({'message': 'Missing schedule information'}), 400

    db.session.commit()

    return jsonify({'message': 'Vendor created successfully'}), 201


@app.route('/api/get_vendors', methods=['GET'])
def get_vendors():
    date_str = request.args.get('date')
    print(date_str)

    if date_str:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        schedules = VendorSchedule.query.filter(VendorSchedule.start_date <= query_date, VendorSchedule.end_date >= query_date).all()
    else:
        schedules = VendorSchedule.query.all()

    vendors_list = []
    for schedule in schedules:
        vendor = Vendor.query.get(schedule.vendor_id)
        user = User.query.get(vendor.user_id)
        vendors_list.append({
            'id': vendor.id,  # Added ID for unique key in React
            'name': vendor.name,
            'link': vendor.link,
            'latitude': schedule.latitude,
            'longitude': schedule.longitude,
            'address': schedule.address,
            'user_name': user.display_name if user else None,
            'user_email': user.email if user else None,
            'start_date': schedule.start_date.isoformat() if schedule.start_date else None,
            'start_time': schedule.start_time.isoformat() if schedule.start_time else None,
            'end_date': schedule.end_date.isoformat() if schedule.end_date else None,
            'end_time': schedule.end_time.isoformat() if schedule.end_time else None
        })
    return jsonify(vendors_list)


@app.route('/api/user_vendors', methods=['GET'])
def get_user_vendors():
    user_email = request.args.get('email')
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    vendors = Vendor.query.filter_by(user_id=user.id).all()
    vendors_list = []

    for vendor in vendors:
        print(vendor.schedules)
        vendors_list.append({
            'id': vendor.id,
            'name': vendor.name,
            'link': vendor.link,
        })

    return jsonify(vendors_list)

@app.route('/api/vendor/<int:vendor_id>', methods=['PUT'])
def update_vendor(vendor_id):
    data = request.get_json()
    print(data)
    email = data.get('email')
    vendor = Vendor.query.filter_by(id=vendor_id).first()
    user = User.query.filter_by(email=email).first()
    
    if not vendor or not user or vendor.user_id != user.id:
        return jsonify({'message': 'Vendor not found or unauthorized'}), 404

    vendor.name = data.get('name', vendor.name)
    vendor.link = data.get('link', vendor.link)

    # Assuming schedules are sent as part of the request
    schedules_data = data.get('schedules', [])
    for schedule_data in schedules_data:
        schedule_id = schedule_data.get('id')
        
        start_time = schedule_data['start_time']
        end_time = schedule_data['end_time']
        # Add redundant second
        if len(start_time) == 5:
            start_time = start_time + ':00'
        if len(end_time) == 5:
            end_time = end_time + ':00'

        # Convert date and time strings to Python date and time objects
        start_date = datetime.strptime(schedule_data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(schedule_data['end_date'], '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time, '%H:%M:%S').time()
        end_time = datetime.strptime(end_time, '%H:%M:%S').time()
        
        print(schedule_id)
        if str(schedule_id).startswith('temp-'):
            new_schedule = VendorSchedule(
                vendor_id=vendor_id,
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=end_time,
                latitude=schedule_data.get('latitude'),
                longitude=schedule_data.get('longitude'),
                address=schedule_data.get('address')
            )
            db.session.add(new_schedule)
        elif schedule_id:
            schedule = VendorSchedule.query.filter_by(id=schedule_id, vendor_id=vendor_id).first()
            if schedule:
                schedule.start_date = start_date
                schedule.start_time = start_time
                schedule.end_date = end_date
                schedule.end_time = end_time
                schedule.latitude = schedule_data.get('latitude', schedule.latitude)
                schedule.longitude = schedule_data.get('longitude', schedule.longitude)
                schedule.address = schedule_data.get('address', schedule.address)

    db.session.commit()
    return jsonify({'message': 'Vendor updated successfully'})

@app.route('/api/vendor/<int:vendor_id>', methods=['DELETE'])
def delete_vendor(vendor_id):
    # Find the vendor by ID
    vendor = Vendor.query.get(vendor_id)

    if not vendor:
        return jsonify({'message': 'Vendor not found'}), 404

    # Delete associated schedules
    VendorSchedule.query.filter_by(vendor_id=vendor_id).delete()

    # Delete the vendor
    db.session.delete(vendor)
    db.session.commit()

    return jsonify({'message': 'Vendor deleted successfully'}), 200

@app.route('/api/vendor/<int:vendor_id>/schedules', methods=['GET'])
def get_vendor_schedules(vendor_id):
    schedules = Vendor.query.filter_by(id=vendor_id).first().schedules
    return jsonify([{
        'id': schedule.id,
        'start_date': schedule.start_date.isoformat(),
        'end_date': schedule.end_date.isoformat(),
        'start_time': schedule.start_time.isoformat(),
        'end_time': schedule.end_time.isoformat(),
        'latitude': schedule.latitude,
        'longitude': schedule.longitude,
        'address': schedule.address
    } for schedule in schedules])

@app.route('/api/schedule/<int:schedule_id>', methods=['DELETE'])
def delete_vendor_schedule(schedule_id):
    schedule = VendorSchedule.query.get(schedule_id)
    print(schedule)
    if schedule:
        db.session.delete(schedule)
        db.session.commit()
        return jsonify({'message': 'Schedule deleted'}), 200
    else:
        return jsonify({'message': 'Schedule not found'}), 200


@app.route('/api/line-callback', methods=['POST'])
def line_callback():
    data = request.json
    code = data['code']
    
    print(code)
    client_id = os.environ['LINE_LOGIN_CLIENT_ID']
    client_secret = os.environ['LINE_LOGIN_CLIENT_SECRET']
    redirect_uri = os.environ['LINE_LOGIN_REDIRECT_URI']

    # Exchange authorization code for access token
    token_url = 'https://api.line.me/oauth2/v2.1/token'
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
    }
    token_response = requests.post(token_url, data=token_data)
    token_json = token_response.json()
    print(token_json)
    if token_response.status_code != 200:
        return jsonify({'success': False, 'message': 'Failed to get access token'})
    
    id_token = token_json['id_token']
    
    user_info_url = 'https://api.line.me/oauth2/v2.1/verify'
    user_info_response = requests.post(user_info_url, data={'id_token': id_token, 'client_id': client_id})
    user_info = user_info_response.json()

    print(user_info)
    user = User.query.filter_by(line_user_id=user_info['sub']).first()

    if not user:
        # Create new user if not exists
        user = User(
            line_user_id=user_info['sub'],
            display_name=user_info['name'],
            email=user_info.get('email', ''),
            picture_url=user_info.get('picture', '')
        )
        db.session.add(user)
        db.session.commit()
    
    return jsonify({
        'success': True,
        'user': {
            'display_name': user.display_name,
            'email': user.email,
            'picture_url': user.picture_url
        }
    })
