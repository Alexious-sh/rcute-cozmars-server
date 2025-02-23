from sanic import Sanic

app = Sanic.get_app("rcute_cozmars_server")
app.run(host="0.0.0.0", port=80, debug=False)
# app.run(host="0.0.0.0", port=80)