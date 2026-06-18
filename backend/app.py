import os

from flask import Flask
from routes.auth import auth_bp

app = Flask(__name__)
app.register_blueprint(auth_bp)

@app.route("/")
def home():
    return {"message": "Shopping App Backend Running"}
print("JWT_SECRET:", os.getenv("JWT_SECRET"))


if __name__ == "__main__":
    app.run(debug=True)