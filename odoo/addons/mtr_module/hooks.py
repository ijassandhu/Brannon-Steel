# -*- coding: utf-8 -*-
import base64

from odoo import api, tools
from odoo import SUPERUSER_ID


def post_init_hook(cr, registry):
    """Ensure the module icon is stored in DB for Apps dashboard tiles."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env["ir.module.module"].search([("name", "=", "mtr_module")], limit=1)
    if not module:
        return

    values = {"icon": "/mtr_module/static/description/icon.png"}
    if "icon_image" in module._fields:
        try:
            with tools.file_open("mtr_module/static/description/icon.png", "rb") as fh:
                values["icon_image"] = base64.b64encode(fh.read())
        except Exception:
            # Fallback to icon path if file read fails for any reason.
            pass

    module.write(values)
