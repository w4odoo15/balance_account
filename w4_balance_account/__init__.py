# -*- coding: utf-8 -*-

from . import models


def post_init_hook(cr, registry):
    from odoo.api import Environment, SUPERUSER_ID
    env = Environment(cr, SUPERUSER_ID, {})
    record = env['account.move.column'].search([('name', '=', 'G-Konto')], limit=1)

    if record and record.report_ids:
        current_ids = record.report_ids.ids
        new_ids = []

        if len(current_ids) >= 2:
            new_ids.append(current_ids[0])
            new_ids.append(record.id)
            new_ids.extend(x for x in current_ids if x not in (current_ids[0], record.id))

            record.report_ids = [(6, 0, new_ids)]
