# -*- coding: utf-8 -*-
"""
    utils.tool
    ~~~~~~~~~~

    Some tool classes and functions.

    :copyright: (c) 2019 by staugur.
    :license: BSD 3-Clause, see LICENSE for more details.
"""

import re
import sys
import hmac
import hashlib
import requests
import smtplib
import semver
from uuid import uuid4
from time import time, localtime, strftime
from datetime import datetime
from random import randrange, sample, randint, choice
from redis import from_url
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
from user_agents import parse as user_agents_parse
from bleach import clean as bleach_clean
from bleach.sanitizer import ALLOWED_TAGS, ALLOWED_ATTRIBUTES, ALLOWED_STYLES
from version import __version__ as PICBED_VERSION
from .log import Logger
from ._compat import string_types, text_type, PY2, urlparse, is_true

if PY2:
    from socket import error as ConnectionRefusedError


logger = Logger("sys").getLogger
err_logger = Logger("error").getLogger
comma_pat = re.compile(r"\s*,\s*")
colon_pat = re.compile(r"\s*:\s*")
verticaline_pat = re.compile(r"\s*\|\s*")
username_pat = re.compile(r"^[a-zA-Z][0-9a-zA-Z\_]{3,31}$")
point_pat = re.compile(r"^\w{1,9}\.?\w{1,9}$")
mail_pat = re.compile(r"([0-9a-zA-Z\_*\.*\-*]+)@([a-zA-Z0-9\-*\_*\.*]+)\.([a-zA-Z]+$)")
author_mail_re = re.compile(r"(.*)\s<(.*)>")
url_pat = re.compile(
    r"^(?:http)s?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
    r"(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)
data_uri_pat = re.compile(
    r"^{}$".format(
        (
            r"data:"
            + r"(?P<mimetype>[\w]+\/[\w\-\+\.]+)?"
            + r"(?:\;charset\=(?P<charset>[\w\-\+\.]+))?"
            + r"(?P<base64>\;base64)?"
            + r",(?P<data>.*)"
        )
    ),
    re.DOTALL,
)
er_pat = re.compile(r"^(and|or|not|\s|ip|ep|origin|method|\(|\))+$")
ir_pat = re.compile(r"^(in|not in|\s|ip|ep|origin|method|,|:)+$")
ALLOWED_RULES = ("ip", "ep", "method", "origin")
ALLOWED_EXTS = ("png", "jpg", "jpeg", "gif", "bmp", "webp")
ALLOWED_HTTP_METHOD = ("GET", "POST", "PUT", "DELETE", "HEAD")
ALLOWED_VIDEO = ("mp4", "ogg", "ogv", "webm", "3gp", "mov")


def rsp(*args):
    """?????? `picbed:` ????????????redis key"""
    return "picbed:" + ":".join(map(str, args))


def md5(text):
    if not PY2 and isinstance(text, text_type):
        text = text.encode("utf-8")
    return hashlib.md5(text).hexdigest()


def sha1(text):
    if not PY2 and isinstance(text, text_type):
        text = text.encode("utf-8")
    return hashlib.sha1(text).hexdigest()


def sha256(text):
    if isinstance(text, text_type):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


def hmac_sha256(key, text):
    if PY2 and isinstance(key, text_type):
        key = key.encode("utf-8")
    if not PY2 and isinstance(key, text_type):
        key = key.encode("utf-8")
    if not PY2 and isinstance(text, text_type):
        text = text.encode("utf-8")
    return hmac.new(key=key, msg=text, digestmod=hashlib.sha256).hexdigest()


def get_current_timestamp(is_float=False):
    """?????????????????????

    :param bool is_float: True?????????10???????????????????????????????????????
    """
    return time() if is_float else int(time())


def timestamp_to_timestring(timestamp, fmt="%Y-%m-%d %H:%M:%S"):
    """????????????(10???)???????????????????????????"""
    if not isinstance(timestamp, (int, float)):
        try:
            timestamp = int(timestamp)
        except (ValueError, TypeError):
            raise
    timestamp = localtime(timestamp)
    return strftime(fmt, timestamp)


def create_redis_engine(redis_url=None):
    """??????redis???????????????

    .. versionchanged:: 1.6.0
        ??????rediscluster
    """
    from config import REDIS

    url = redis_url or REDIS
    if not url:
        return
    if url.startswith("rediscluster://"):
        try:
            from rediscluster import RedisCluster
        except ImportError:
            raise ImportError(
                "Please install module with `pip install redis-py-cluster`"
            )
        else:
            startup_nodes = [
                dict(host=hp.split(":")[0], port=hp.split(":")[1])
                for hp in comma_pat.split(url.split("://")[-1])
                if hp and len(hp.split(":")) == 2
            ]
            if startup_nodes:
                return RedisCluster(startup_nodes=startup_nodes, decode_responses=True)
            else:
                raise ValueError("Invalid redis url")
    return from_url(url, decode_responses=True)


def gen_rnd_filename(fmt):
    if fmt == "time1":
        return int(round(time() * 1000))
    elif fmt == "time2":
        return "%s%s" % (
            int(round(time() * 1000)),
            str(randrange(1000, 10000)),
        )
    elif fmt == "time3":
        return "%s%s" % (
            datetime.now().strftime("%Y%m%d%H%M%S"),
            str(randrange(1000, 10000)),
        )


def get_today(fmt="%Y/%m/%d"):
    return datetime.now().strftime(fmt)


def allowed_file(filename, suffix=None):
    if not filename:
        return False
    suffix = set(suffix or ALLOWED_EXTS)
    return "." in filename and filename.rsplit(".", 1)[1].lower() in suffix


def parse_valid_comma(s):
    if isinstance(s, string_types):
        return [i for i in comma_pat.split(s) if i]


def parse_valid_verticaline(s):
    if isinstance(s, string_types):
        return [i for i in verticaline_pat.split(s) if i]


def parse_valid_colon(s):
    """???????????? a:b,x:y ???????????? dict(a=b, x=y)"""
    if s:
        return dict(
            [
                i.split(":")
                for i in comma_pat.split(s)
                if i
                and ":" in i
                and len(i.split(":")) == 2
                and i.split(":")[0]
                and i.split(":")[1]
            ]
        )


def list_equal_split(alist, n=5):
    return [alist[i : i + n] for i in range(0, len(alist), n)]


def generate_random(length=6):
    code_list = []
    for i in range(10):  # 0-9??????
        code_list.append(str(i))
    for i in range(65, 91):  # A-Z
        code_list.append(chr(i))
    for i in range(97, 123):  # a-z
        code_list.append(chr(i))
    myslice = sample(code_list, length)
    return "".join(myslice)


def format_upload_src(fmt, value):
    """??????upload??????????????????src??????"""
    if fmt and isinstance(fmt, string_types):
        if point_pat.match(fmt):
            if "." in fmt:
                fmts = fmt.split(".")
                return {fmts[0]: {fmts[1]: value}}
            else:
                return {fmt: value}
    return dict(src=value)


def format_apires(res, sn="code", oc=None, mn=None):
    """??????API??????JSON?????????

    ??????????????????????????????????????????res???????????????

    - sn: status_name??????????????????????????????????????????code
    - oc: ok_code?????????????????????????????????0???????????????bool????????????????????????
    - mn: msg_name??????????????????????????????????????????msg
    """
    if isinstance(res, dict) and "code" in res:
        if not sn:
            sn = "code"
        code = res.pop("code")
        if oc:
            if oc == "bool":
                #: ok_code??????bool??????????????????True?????????False
                code = True if code == 0 else False
            else:
                #: ??????bool??????int???????????????oc????????????code??????
                try:
                    code = int(oc) if code == 0 else code
                except (ValueError, TypeError):
                    pass
        res[sn] = code
        if mn and res.get("msg"):
            msg = res.pop("msg")
            res[mn] = msg
    return res


class Attribution(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class Attribute(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return ""


def get_origin(url):
    """???url???????????????CORS?????????origin??????"""
    parsed_uri = urlparse(url)
    return "{uri.scheme}://{uri.netloc}".format(uri=parsed_uri)


def check_origin(addr):
    """Check whether UrlAddr is in a valid host origin, for example:

    .. code-block::

        http://ip:port
        https://abc.com
    """
    if addr and isinstance(addr, string_types):
        try:
            origin = get_origin(addr)
        except (ValueError, TypeError, Exception):
            return False
        else:
            return url_pat.match(origin)
    return False


def check_url(addr):
    """Check whether UrlAddr is in a valid format"""
    if addr and isinstance(addr, string_types):
        if url_pat.match(addr):
            return True
    return False


def check_ip(ip_str):
    sep = ip_str.split(".")
    if len(sep) != 4:
        return False
    for x in sep:
        try:
            int_x = int(x)
            if int_x < 0 or int_x > 255:
                return False
        except ValueError:
            return False
    return True


def gen_uuid():
    return uuid4().hex


def check_ir(ir):
    """??????ir?????????????????????: in:opt1, not in:opt2"""
    if ir:
        for i in parse_valid_comma(ir):
            opr, opt = i.split(":")
            if opt not in ALLOWED_RULES or opr not in ("in", "not in"):
                raise ValueError


def parse_data_uri(datauri):
    """Parse Data URLs: data:[<media type>][;base64],<data>"""
    if not PY2 and not isinstance(datauri, text_type):
        datauri = datauri.decode("utf-8")
    match = data_uri_pat.match(datauri)
    if match:
        mimetype = match.group("mimetype") or None
        charset = match.group("charset") or None
        is_base64 = bool(match.group("base64"))
        data = match.group("data")
    else:
        mimetype = charset = data = None
        is_base64 = False

    return Attribution(
        dict(
            mimetype=mimetype,
            charset=charset,
            is_base64=is_base64,
            data=data,
        )
    )


def gen_ua():
    """????????????????????????"""
    first_num = randint(55, 62)
    third_num = randint(0, 3200)
    fourth_num = randint(0, 140)
    os_type = [
        "(Windows NT 6.1; WOW64)",
        "(Windows NT 10.0; WOW64)",
        "(X11; Linux x86_64)",
        "(Macintosh; Intel Mac OS X 10_12_6)",
    ]
    chrome_version = "Chrome/{}.0.{}.{}".format(first_num, third_num, fourth_num)
    ua = " ".join(
        [
            "Mozilla/5.0",
            choice(os_type),
            "AppleWebKit/537.36",
            "(KHTML, like Gecko)",
            chrome_version,
            "Safari/537.36",
        ]
    )
    return ua


def parse_ua(user_agent):
    """????????????????????????????????????????????????????????????"""
    uap = user_agents_parse(user_agent)
    device, ua_os, family = str(uap).split(" / ")
    if uap.is_mobile:
        platform = "mobile"
    elif uap.is_pc:
        platform = "pc"
    elif uap.is_tablet:
        platform = "tablet"
    elif uap.is_bot:
        platform = "bot"
    else:
        platform = "other"
    if (
        user_agent.startswith("picbed-cli") or user_agent.startswith("sapicli")
    ) and user_agent.endswith("amd64"):
        _, _, ua_os, device = user_agent.split(" ")
        family = "sapicli"
    return dict(platform=platform, device=device, os=ua_os, family=family)


def slash_join(*args):
    """??? / ????????????"""
    stripped_strings = []
    for a in args:
        if a[0] == "/":
            start = 1
        else:
            start = 0
        if a[-1] == "/":
            stripped_strings.append(a[start:-1])
        else:
            stripped_strings.append(a[start:])
    return "/".join(stripped_strings)


def try_request(
    url,
    params=None,
    data=None,
    headers=None,
    timeout=5,
    method="post",
    proxy=None,
    num_retries=1,
    _is_retry=False,
):
    """
    :param dict params: ??????????????????
    :param dict data: ??????????????????
    :param int timeout: ????????????????????????
    :param str method: ???????????????get???post???put???delete
    :param str proxy: ?????????????????????
    :param int num_retries: ??????????????????
    :param bool _is_retry: ???????????????????????????????????????????????????
    """
    headers = headers or {}
    if "User-Agent" not in headers:
        headers["User-Agent"] = "sapic/v%s" % PICBED_VERSION
    method = method.lower()
    if method == "get":
        method_func = requests.get
    elif method == "post":
        method_func = requests.post
    elif method == "put":
        method_func = requests.put
    elif method == "delete":
        method_func = requests.delete
    else:
        method_func = requests.post
    try:
        resp = method_func(
            url,
            params=params,
            headers=headers,
            data=data,
            timeout=timeout,
            proxies=proxy if _is_retry is True and proxy else None,
        )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        if num_retries > 0:
            return try_request(
                url,
                params=params,
                data=data,
                headers=headers,
                timeout=timeout,
                method=method,
                proxy=proxy,
                num_retries=num_retries - 1,
                _is_retry=True,
            )
        else:
            raise
    except (requests.exceptions.RequestException, Exception):
        raise
    else:
        return resp


def is_venv():
    """???????????????????????????virtualenv???venv???"""
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def is_all_fail(alist):
    """???list??????dict??????code!=0???(????????????)??????"""
    return len(alist) == len(list(filter(lambda x: x.get("code") != 0, alist)))


def check_to_addr(to):
    """?????????????????????"""
    to_addrs = parse_valid_comma(to)
    if to_addrs:
        for to in to_addrs:
            if not mail_pat.match(to):
                return False
        return True


class Mailbox(object):
    def __init__(self, user, passwd, smtp_server, smtp_port=25):
        """?????????????????????????????????

        :param user: ????????????
        :param passwd: ????????????????????????????????????
        :param smtp_server: ?????????SMTP???????????????
        """
        self._user = user
        self._passwd = passwd
        self._server = smtp_server
        self._port = smtp_port
        self._ssl = False if self._port == 25 else True
        self._debug = False

    @property
    def ssl(self):
        """?????????????????????????????????setter"""
        return self._ssl

    @ssl.setter
    def ssl(self, smtp_ssl):
        self._ssl = is_true(smtp_ssl)

    @property
    def debug(self):
        """????????????debug???????????????setter"""
        return self._debug

    @debug.setter
    def debug(self, level):
        if isinstance(level, int) or level is False:
            self._debug = level

    def _format_addr(self, s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, "utf-8").encode(), addr))

    def send(self, subject, message, to_addrs, from_name=None):
        """Sendmail

        :param subject: ????????????
        :param message: ???????????????HTML
        :param to_addrs: ????????????????????????
        :returns: send result
        :rtype: dict
        """
        res = dict(code=1)
        if subject and message and to_addrs:
            if not isinstance(to_addrs, (list, tuple)):
                to_addrs = (to_addrs,)
            msg = MIMEText(message, "html", "utf-8")
            msg["from"] = self._format_addr(
                "{0} <{1}>".format(from_name or self._user.split("@")[0], self._user)
            )
            msg["to"] = ";".join(to_addrs)
            msg["subject"] = Header(subject, "utf-8").encode()
            try:
                if self._ssl is True:
                    server = smtplib.SMTP_SSL(self._server, self._port)
                else:
                    server = smtplib.SMTP(self._server, self._port)
                if self._debug:  # not False, > 0
                    server.set_debuglevel(self._debug)
                if self._user and self._passwd:
                    server.login(self._user, self._passwd)
                server.sendmail(self._user, to_addrs, msg.as_string())
                server.quit()
            except (smtplib.SMTPException, ConnectionRefusedError) as e:
                res.update(msg=str(e))
            else:
                res.update(code=0)
        else:
            res.update(msg="Bad mailbox params")
        return res


def bleach_html(
    html,
    tags=ALLOWED_TAGS,
    attrs=ALLOWED_ATTRIBUTES,
    styles=ALLOWED_STYLES,
):
    return bleach_clean(
        html,
        tags=tags,
        attributes=attrs,
        styles=styles,
    )


def is_valid_verion(version):
    """Semantic version number - determines whether the version is qualified.
    The format is MAJOR.Minor.PATCH, more with https://semver.org

    :param str version: ?????????
    """
    if not version:
        return False
    if not PY2 and not isinstance(version, string_types):
        version = version.decode("utf-8")

    if hasattr(semver.VersionInfo, "isvalid"):
        return semver.VersionInfo.isvalid(version or "")

    try:
        semver.parse(version)
    except (TypeError, ValueError):
        return False
    else:
        return True


def is_match_appversion(appversion=None):
    """????????????????????????????????????appversion??????

    :param str appversion: ?????????????????????????????????????????????
    """
    #: ????????????appversion?????????????????????????????????
    if not appversion:
        return True
    if not PY2 and not isinstance(appversion, string_types):
        appversion = appversion.decode("utf-8")

    sysver = semver.VersionInfo.parse(PICBED_VERSION)

    def vermatch(check_ver):
        try:
            return sysver.match(check_ver)
        except ValueError:
            return sysver.match(">={}".format(check_ver))

    avs = comma_pat.split(appversion)
    for v in avs:
        if not vermatch(v):
            return False
    else:
        return True


def less_latest_tag(latest_tag):
    """????????????????????????GitHub??????????????????"""
    if latest_tag and is_valid_verion(latest_tag):
        return semver.compare(latest_tag, PICBED_VERSION) == 1


def parse_author_mail(author):
    """????????? ``author <author-mail>`` ?????????author???mail"""
    pat = author_mail_re.search(author)
    return (pat.group(1), pat.group(2)) if pat else (author, None)


def parse_label(label):
    if label:
        label = parse_valid_comma(label)
    else:
        label = []
    if isinstance(label, (list, tuple)):
        return label
    return []


def b64size(b64string):
    """??????base64?????????????????????bytes"""
    return (len(b64string) * 3) / 4 - b64string.count("=", -2)
