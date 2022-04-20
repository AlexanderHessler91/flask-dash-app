from flask import Flask, render_template
from dash_app import create_dash_app
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")



create_dash_app(app)

if __name__ == "__main__":
    app.run(debug=True)