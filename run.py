import os

from app import create_app

app = create_app()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

if __name__ == '__main__':
    app.run(debug=app.config['APP_ENV'] == 'development', host=HOST, port=PORT)
