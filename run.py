
from app import create_app , socketio

app = create_app()

if __name__ == "__main__":
    print(" >>> Bấm vào link này để mở: http://127.0.0.1:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)