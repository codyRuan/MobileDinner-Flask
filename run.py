from app import app, db
from app.models import User, Vendor, Favorite

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Vendor': Vendor, 'Favorite': Favorite}

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)