from rcute_cozmars_server import create_app
from sanic.worker.loader import AppLoader
from functools import partial

app_loader = AppLoader(factory=partial(create_app, __name__))
app = app_loader.load()
app.run(host="0.0.0.0", port=80, debug=False)
# app.run(host="0.0.0.0", port=80)