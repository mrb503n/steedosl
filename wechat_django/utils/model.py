# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re

from django.utils.translation import ugettext_lazy as _


def enum2choices(enum):
    pattern = re.compile(r"^[A-Z][A-Z_\d]+$")
    return tuple(
        (getattr(enum, key), _(key))
        for key in dir(enum)
        if re.match(pattern, key)
    )
