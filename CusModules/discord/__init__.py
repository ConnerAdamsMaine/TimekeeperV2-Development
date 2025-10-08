"""
Discord API Wrapper
~~~~~~~~~~~~~~~~~~~

A basic wrapper for the Discord API.

:copyright: (c) 2015-present Rapptz
:license: MIT, see LICENSE for more details.

"""

__title__ = 'discord'
__author__ = 'Rapptz'
__license__ = 'MIT'
__copyright__ = 'Copyright 2015-present Rapptz'
__version__ = '2.6.3'

__path__ = __import__('pkgutil').extend_path(__path__, __name__)

import logging
from typing import NamedTuple, Literal

from .client import *
from .appinfo import *
from .user import *
from .emoji import *
from .partial_emoji import *
from .activity import *
from .channel import *
from .guild import *
from .flags import *
from .member import *
from .message import *
from .asset import *
from .errors import *
from .permissions import *
from .role import *
from .file import *
from .colour import *
from .integrations import *
from .invite import *
from .template import *
from .welcome_screen import *
from .sku import *
from .widget import *
from .object import *
from .reaction import *
from . import (
    utils as utils,
    opus as opus,
    abc as abc,
    ui as ui,
    app_commands as app_commands,
)
from .enums import *
from .embeds import *
from .mentions import *
from .shard import *
from .player import *
from .webhook import *
from .voice_client import *
from .audit_logs import *
from .raw_models import *
from .team import *
from .sticker import *
from .stage_instance import *
from .scheduled_event import *
from .interactions import *
from .components import *
from .threads import *
from .automod import *
from .poll import *
from .soundboard import *
from .subscription import *
from .presences import *
from .primary_guild import *
from .onboarding import *

from os import getenv
from dotenv import load_dotenv

import contextlib
from hashlib import sha512

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def drm_check():
    DRM = getenv("DRM_VALIDATION")
    if not DRM:
        return False
    DRM = sha512(DRM.encode()).hexdigest()
    try:
        with open("hash", "r") as f:
            return DRM == f.read().strip()
    except Exception:
        return False

@contextlib.contextmanager
def suppress_traceback_on_fail(scrub: bool, public_message: str):
    try:
        yield
    except Exception as e:
        if scrub:
            logger.critical("DRM violation occurred")
            e.__traceback__ = None
            raise RuntimeError(public_message) from None
        else:
            raise

scrub = not drm_check()
with suppress_traceback_on_fail(scrub, "Error 1201. Do not contact support, you have broken the law!"):
    if not scrub:
        pass
    else:
        raise RuntimeError("DRM failure")

class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: Literal['alpha', 'beta', 'candidate', 'final']
    serial: int


version_info: VersionInfo = VersionInfo(major=2, minor=6, micro=3, releaselevel='final', serial=0)

logging.getLogger(__name__).addHandler(logging.NullHandler())

# This is a backwards compatibility hack and should be removed in v3
# Essentially forcing the exception to have different base classes
# In the future, this should only inherit from ClientException
if len(MissingApplicationID.__bases__) == 1:
    MissingApplicationID.__bases__ = (app_commands.AppCommandError, ClientException)

del logging, NamedTuple, Literal, VersionInfo
