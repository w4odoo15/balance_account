# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from odoo import models, fields, api, _
from odoo.tools import get_lang, SQL

_logger = logging.getLogger(__name__)
class AccountMoveColumn(models.Model):
    _inherit="account.move.column"

    def init(self):
       record = self.env['account.move.column'].search([('name', "=", "G-Konto")])

       current_ids = self.report_ids.ids
       
       new_ids = []
       
       if current_ids and len(current_ids) > 2:
            new_ids.append(current_ids[0])
            new_ids.append(record.id)
            new_ids.extend(x for x in current_ids if x != current_ids[0] and x != current_ids[1])

            self.report_ids = [(6, 0, new_ids)]

    
class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    bal_acc = fields.Char(compute="_compute_bal_acc",store=True)
    
    @api.depends('debit','credit','move_id','move_id.state')
    def _compute_bal_acc(self):
        for rec in self:
            bal_acc = 'div'

            _logger.info("Processing record: %s, Debit: %s, Credit: %s", rec.id, rec.debit, rec.credit)
            _logger.info("rec.move_id: %s", rec.move_id)
            _logger.info("debit: %s", rec.debit)
            
            if rec.move_id and rec.debit > 0.0:
                line = self.env['account.move.line'].search([('move_id','=',rec.move_id.id),('id','!=',rec.id),('credit','=',rec.debit)],limit=1)
                if line:
                   bal_acc = line.account_id.code 
                else:
                    bal_acc = 'div'
            elif rec.move_id and rec.credit > 0.0:
                line = self.env['account.move.line'].search([('move_id','=',rec.move_id.id),('id','!=',rec.id),('debit','=',rec.credit)],limit=1)
                if line:
                   bal_acc = line.account_id.code
                else:
                    bal_acc = 'div'

            _logger.info("bal_acc %s", bal_acc)
            rec.bal_acc = bal_acc

class GeneralLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _get_query_amls(self, report, options, expanded_account_ids, offset=0, limit=None):
        """ Construct a query retrieving the account.move.lines when expanding a report line with or without the load more. """
        additional_domain = [('account_id', 'in', expanded_account_ids)] if expanded_account_ids is not None else None
        queries = []
        journal_name = self.env['account.journal']._field_to_sql('journal', 'name')
        for column_group_key, group_options in report._split_options_per_column_group(options).items():
            query = report._get_report_query(group_options, domain=additional_domain, date_scope='strict_range')
            account_alias = query.left_join(lhs_alias='account_move_line', lhs_column='account_id', rhs_table='account_account', rhs_column='id', link='account_id')
            account_code = self.env['account.account']._field_to_sql(account_alias, 'code', query)
            account_name = self.env['account.account']._field_to_sql(account_alias, 'name')
            account_type = self.env['account.account']._field_to_sql(account_alias, 'account_type')

            sql_query = SQL(
                '''
                SELECT
                    account_move_line.id,
                    account_move_line.date,
                    account_move_line.date_maturity,
                    account_move_line.name AS name,
                    account_move_line.ref,
                    account_move_line.company_id,
                    account_move_line.account_id,
                    account_move_line.payment_id,
                    account_move_line.partner_id,
                    account_move_line.currency_id,
                    account_move_line.amount_currency,
                    COALESCE(account_move_line.invoice_date, account_move_line.date) AS invoice_date,
                    %(debit_select)s  AS debit,
                    %(credit_select)s AS credit,
                    %(balance_select)s AS balance,
                    move.name AS move_name,
                    company.currency_id AS company_currency_id,
                    account_move_line.bal_acc AS bal_acc,
                    partner.name AS partner_name,
                    move.move_type AS move_type,
                    %(account_code)s AS account_code,
                    %(account_name)s AS account_name,
                    %(account_type)s AS account_type,
                    journal.code AS journal_code,
                    %(journal_name)s AS journal_name,
                    full_rec.id AS full_rec_name,
                    %(column_group_key)s AS column_group_key
                FROM %(table_references)s
                JOIN account_move move ON move.id = account_move_line.move_id
                %(currency_table_join)s
                LEFT JOIN res_company company ON company.id = account_move_line.company_id
                LEFT JOIN res_partner partner ON partner.id = account_move_line.partner_id
                LEFT JOIN account_account account ON account.id = account_move_line.account_id
                LEFT JOIN account_journal journal ON journal.id = account_move_line.journal_id
                LEFT JOIN account_full_reconcile full_rec ON full_rec.id = account_move_line.full_reconcile_id
                WHERE %(search_condition)s
                ORDER BY account_move_line.date, move.name, account_move_line.id
                ''',
                account_code=account_code,
                account_name=account_name,
                account_type=account_type,
                journal_name=journal_name,
                column_group_key=column_group_key,
                table_references=query.from_clause,
                currency_table_join=report._currency_table_aml_join(group_options),
                debit_select=report._currency_table_apply_rate(SQL("account_move_line.debit")),
                credit_select=report._currency_table_apply_rate(SQL("account_move_line.credit")),
                balance_select=report._currency_table_apply_rate(SQL("account_move_line.balance")),
                search_condition=query.where_clause,
            )
            queries.append(sql_query)

        full_query = SQL(" UNION ALL ").join(SQL("(%s)", query) for query in queries)

        if offset:
            full_query = SQL('%s OFFSET %s ', full_query, offset)
        if limit:
            full_query = SQL('%s LIMIT %s ', full_query, limit)

        _logger.info("Generated SQL query: %s", full_query)
        _logger.info("Query execution started")
        return full_query
