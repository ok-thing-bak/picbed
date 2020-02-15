# -*- coding: utf-8 -*-
"""
    app
    ~~~

    Entrance

    :copyright: (c) 2019 by staugur.
    :license: BSD 3-Clause, see LICENSE for more details.
"""

from uuid import uuid4
from flask import Flask, g, request, render_template
from version import __version__
from views import front_bp, api_bp
from utils.tool import Attribute, is_true, parse_valid_comma, err_logger, \
    create_redis_engine
from utils.web import get_site_config, JsonResponse, default_login_auth, \
    get_redirect_url
from utils.cli import sa_cli
from libs.hook import HookManager
from config import GLOBAL

__author__ = 'staugur'
__email__ = 'staugur@saintic.com'
__date__ = '2019-12-20'
__doc__ = 'Flask-based Web self-built pictures bed'

app = Flask(__name__)
app.response_class = JsonResponse
app.config.update(
    SECRET_KEY=GLOBAL.get("SecretKey") or str(uuid4()),
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
)

hm = HookManager(app)
rc = create_redis_engine()

app.register_blueprint(front_bp)
app.register_blueprint(api_bp, url_prefix="/api")
app.cli.add_command(sa_cli)


@app.context_processor
def GlobalTemplateVariables():
    return {"Version": __version__, "is_true": is_true}


@app.before_request
def before_request():
    g.rc = rc
    g.signin, g.userinfo = default_login_auth()
    #: Trigger hook, you can modify flask.g
    hm.call("before_request")
    #: No Required field
    g.site = get_site_config()
    g.cfg = Attribute(g.site)
    #: Required field: username, is_admin
    g.userinfo = Attribute(g.userinfo)
    g.is_admin = is_true(g.userinfo.is_admin)
    g.next = get_redirect_url()


@app.after_request
def after_request(res):
    #: Trigger hook, you can modify the response
    hm.call("after_request", res=res)
    if g.cfg.cors:
        if g.cfg.cors == "*":
            res.headers.add("Access-Control-Allow-Origin", "*")
        else:
            cors = parse_valid_comma(g.cfg.cors)
            origin = request.headers.get("Origin")
            if origin in cors:
                res.headers.add("Access-Control-Allow-Origin", origin)
    return res


@app.errorhandler(500)
@app.errorhandler(404)
@app.errorhandler(403)
@app.errorhandler(413)
def page_error(e):
    if getattr(e, "code", None) == 500:
        err_logger.error(e, exc_info=True)
    return render_template("public/error.html", e=e)
