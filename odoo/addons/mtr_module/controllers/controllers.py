# -*- coding: utf-8 -*-
import json
import logging

import requests

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

_FIELD_MAP = {
    "heat_number": "mtr_heat_number",
    "batch_number": "mtr_batch_number",
    "grade": "mtr_grade",
    "manufacturer": "mtr_manufacturer",
    "certificate_number": "mtr_certificate_number",
    "certificate_date": "mtr_certificate_date",
    "country_of_melt": "mtr_country_of_melt",
    "country_of_manufacture": "mtr_country_of_manufacture",
    "lot_number": "inv_lot_number",
    "item_no": "inv_item_no",
    "slab_number": "inv_slab_number",
    "inventory_heat_number": "inv_heat_number",
    "inventory_grade": "inv_grade",
    "c": "mtr_c",
    "mn": "mtr_mn",
    "si": "mtr_si",
    "p": "mtr_p",
    "s": "mtr_s",
    "cu": "mtr_cu",
    "ni": "mtr_ni",
    "cr": "mtr_cr",
    "mo": "mtr_mo",
    "n": "mtr_n",
    "yield_strength": "mtr_yield_strength",
    "tensile_strength": "mtr_tensile_strength",
    "elongation": "mtr_elongation",
    "reduction_area": "mtr_reduction_area",
    "hardness": "mtr_hardness",
    "impact_test_temp": "mtr_impact_test_temp",
    "impact_coupon_size": "mtr_impact_coupon_size",
    "impact_specimen_1": "mtr_impact_specimen_1",
    "impact_specimen_2": "mtr_impact_specimen_2",
    "impact_specimen_3": "mtr_impact_specimen_3",
    "impact_average": "mtr_impact_average",
}

_FIELD_ALIASES = {
    # heat / batch / grade / manufacturer
    "heat": "heat_number",
    "heatno": "heat_number",
    "heat_no": "heat_number",
    "heatnumber": "heat_number",
    "batch": "batch_number",
    "batchno": "batch_number",
    "batch_no": "batch_number",
    "batchnumber": "batch_number",
    "mat": "grade",
    "material": "grade",
    "material_grade": "grade",
    "materialgrade": "grade",
    "spec": "grade",
    "specification": "grade",
    "mfg": "manufacturer",
    "mill": "manufacturer",
    "supplier": "manufacturer",
    "cert": "certificate_number",
    "certno": "certificate_number",
    "cert_no": "certificate_number",
    "certnumber": "certificate_number",
    "certificate": "certificate_number",
    "certdate": "certificate_date",
    "cert_date": "certificate_date",
    "certificate_date": "certificate_date",
    # origin
    "melt_country": "country_of_melt",
    "melt": "country_of_melt",
    "com": "country_of_manufacture",
    "country_of_manufacture": "country_of_manufacture",
    # inventory
    "lot": "lot_number",
    "lotno": "lot_number",
    "lot_no": "lot_number",
    "item": "item_no",
    "itemno": "item_no",
    "item_no": "item_no",
    "slab": "slab_number",
    "slabno": "slab_number",
    "slab_no": "slab_number",
    "inv_heat": "inventory_heat_number",
    "inventory_heat": "inventory_heat_number",
    "inv_grade": "inventory_grade",
    # chemistry
    "carbon": "c",
    "c%": "c",
    "manganese": "mn",
    "mn%": "mn",
    "silicon": "si",
    "si%": "si",
    "phosphorus": "p",
    "p%": "p",
    "sulfur": "s",
    "s%": "s",
    "copper": "cu",
    "cu%": "cu",
    "nickel": "ni",
    "ni%": "ni",
    "chromium": "cr",
    "cr%": "cr",
    "molybdenum": "mo",
    "mo%": "mo",
    "nitrogen": "n",
    "n%": "n",
    # mechanical
    "ys": "yield_strength",
    "yield": "yield_strength",
    "yieldstrength": "yield_strength",
    "yield_strength": "yield_strength",
    "ys_ksi": "yield_strength",
    "uts": "tensile_strength",
    "tensile": "tensile_strength",
    "tensilestrength": "tensile_strength",
    "tensile_strength": "tensile_strength",
    "elong": "elongation",
    "elongation": "elongation",
    "ra": "reduction_area",
    "reductionarea": "reduction_area",
    "reduction_area": "reduction_area",
    "hard": "hardness",
    "hardness": "hardness",
    "hrb": "hardness",
    "hrc": "hardness",
    # impact
    "impact": "impact_average",
    "charpy": "impact_average",
    "impact_average": "impact_average",
    "impactavg": "impact_average",
    "impact_temp": "impact_test_temp",
    "impact_test_temp": "impact_test_temp",
    "impact_cpn_size": "impact_coupon_size",
    "impact_coupon_size": "impact_coupon_size",
    "impact1": "impact_specimen_1",
    "impact_1": "impact_specimen_1",
    "impact2": "impact_specimen_2",
    "impact_2": "impact_specimen_2",
    "impact3": "impact_specimen_3",
    "impact_3": "impact_specimen_3",
}

_MTR_FIELD_MAP = {
    "heat_number": "heat_number",
    "batch_number": "batch_number",
    "grade": "grade",
    "manufacturer": "manufacturer",
    "certificate_number": "certificate_number",
    "certificate_date": "certificate_date",
    "country_of_melt": "country_of_melt",
    "country_of_manufacture": "country_of_manufacture",
    "c": "c_element",
    "mn": "mn_element",
    "si": "si_element",
    "p": "p_element",
    "s": "s_element",
    "cu": "cu_element",
    "ni": "ni_element",
    "cr": "cr_element",
    "mo": "mo_element",
    "n": "n_element",
    "yield_strength": "yield_strength",
    "tensile_strength": "tensile_strength",
    "elongation": "elongation",
    "reduction_area": "reduction_area",
    "hardness": "hardness",
    "impact_test_temp": "impact_test_temp",
    "impact_coupon_size": "impact_coupon_size",
    "impact_specimen_1": "impact_specimen_1",
    "impact_specimen_2": "impact_specimen_2",
    "impact_specimen_3": "impact_specimen_3",
    "impact_average": "impact_average",
}

_NUMERIC_FIELDS = {
    "mtr_c",
    "mtr_mn",
    "mtr_si",
    "mtr_p",
    "mtr_s",
    "mtr_cu",
    "mtr_ni",
    "mtr_cr",
    "mtr_mo",
    "mtr_n",
    "mtr_yield_strength",
    "mtr_tensile_strength",
    "mtr_elongation",
    "mtr_reduction_area",
    "mtr_hardness",
    "mtr_impact_test_temp",
    "mtr_impact_specimen_1",
    "mtr_impact_specimen_2",
    "mtr_impact_specimen_3",
    "mtr_impact_average",
}

_MTR_NUMERIC_FIELDS = {
    "c_element",
    "mn_element",
    "si_element",
    "p_element",
    "s_element",
    "cu_element",
    "ni_element",
    "cr_element",
    "mo_element",
    "n_element",
    "yield_strength",
    "tensile_strength",
    "elongation",
    "reduction_area",
    "hardness",
    "impact_test_temp",
    "impact_specimen_1",
    "impact_specimen_2",
    "impact_specimen_3",
    "impact_average",
}

_TEXT_FIELDS = {
    "mtr_heat_number",
    "mtr_batch_number",
    "mtr_grade",
    "mtr_manufacturer",
    "mtr_certificate_number",
    "mtr_country_of_melt",
    "mtr_country_of_manufacture",
    "inv_lot_number",
    "inv_item_no",
    "inv_slab_number",
    "inv_heat_number",
    "inv_grade",
}

_MTR_TEXT_FIELDS = {
    "heat_number",
    "batch_number",
    "grade",
    "manufacturer",
    "certificate_number",
    "country_of_melt",
    "country_of_manufacture",
}

_TEXT_SEARCH_FIELDS = [
    "mtr_heat_number",
    "mtr_batch_number",
    "mtr_grade",
    "mtr_manufacturer",
    "mtr_certificate_number",
    "inv_lot_number",
    "inv_item_no",
    "inv_description",
    "inv_heat_number",
    "inv_slab_number",
]

_MTR_TEXT_SEARCH_FIELDS = [
    "heat_number",
    "batch_number",
    "grade",
    "manufacturer",
    "certificate_number",
]

_ALLOWED_OPS = {"=", "!=", ">=", "<=", ">", "<", "ilike", "not ilike"}


def _extract_json(text):
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def _coerce_value(field, value, numeric_fields=None):
    if value is None:
        return None
    numeric_fields = numeric_fields or _NUMERIC_FIELDS
    if field in numeric_fields:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return value


def _or_domain(clauses):
    clauses = [clause for clause in clauses if clause]
    if not clauses:
        return []
    if len(clauses) == 1:
        return [clauses[0]]
    return ["|"] * (len(clauses) - 1) + clauses


def _build_filters_domain(filters):
    domain = []
    for entry in filters or []:
        field_key = (entry.get("field") or "").strip().lower()
        field_key = _FIELD_ALIASES.get(field_key, field_key)
        op = (entry.get("op") or "=").strip()
        value = entry.get("value")
        field = _FIELD_MAP.get(field_key)
        if not field or op not in _ALLOWED_OPS:
            continue
        value = _coerce_value(field, value, _NUMERIC_FIELDS)
        if value in (None, ""):
            continue
        if op == "=" and field in _TEXT_FIELDS and isinstance(value, str):
            op = "ilike"
        elif op == "!=" and field in _TEXT_FIELDS and isinstance(value, str):
            op = "not ilike"
        domain.append((field, op, value))
    return domain


def _build_text_domain(text_query):
    if not text_query:
        return []
    clauses = [(field, "ilike", text_query) for field in _TEXT_SEARCH_FIELDS]
    return _or_domain(clauses)


def _build_mtr_filters_domain(filters):
    domain = []
    for entry in filters or []:
        field_key = (entry.get("field") or "").strip().lower()
        field_key = _FIELD_ALIASES.get(field_key, field_key)
        op = (entry.get("op") or "=").strip()
        value = entry.get("value")
        field = _MTR_FIELD_MAP.get(field_key)
        if not field or op not in _ALLOWED_OPS:
            continue
        value = _coerce_value(field, value, _MTR_NUMERIC_FIELDS)
        if value in (None, ""):
            continue
        if op == "=" and field in _MTR_TEXT_FIELDS and isinstance(value, str):
            op = "ilike"
        elif op == "!=" and field in _MTR_TEXT_FIELDS and isinstance(value, str):
            op = "not ilike"
        domain.append((field, op, value))
    return domain


def _build_mtr_text_domain(text_query):
    if not text_query:
        return []
    clauses = [(field, "ilike", text_query) for field in _MTR_TEXT_SEARCH_FIELDS]
    return _or_domain(clauses)


def _call_openai_parser(message, api_key, model):
    system_prompt = (
        "You extract search filters from user queries about MTR and inventory data. "
        "Return ONLY valid JSON with this shape: "
        "{\"filters\":[{\"field\":\"heat_number\",\"op\":\"=\",\"value\":\"H100\"}],"
        "\"text_query\":\"optional\","
        "\"limit\":20}. "
        "Map common aliases to fields: "
        "c/carbon -> c, mn/manganese -> mn, si/silicon -> si, p/phosphorus -> p, s/sulfur -> s, "
        "cu/copper -> cu, ni/nickel -> ni, cr/chromium -> cr, mo/molybdenum -> mo, n/nitrogen -> n, "
        "yield strength/ys -> yield_strength, tensile/uts -> tensile_strength, "
        "elongation/elong -> elongation, reduction area/ra -> reduction_area, "
        "hardness/hrb/hrc -> hardness, impact/charpy -> impact_average. "
        "Valid fields: heat_number, batch_number, grade, manufacturer, certificate_number, "
        "certificate_date, country_of_melt, country_of_manufacture, lot_number, item_no, "
        "slab_number, inventory_heat_number, inventory_grade, c, mn, si, p, s, cu, ni, cr, mo, n, "
        "yield_strength, tensile_strength, elongation, reduction_area, hardness, impact_test_temp, "
        "impact_coupon_size, impact_specimen_1, impact_specimen_2, impact_specimen_3, impact_average. "
        "Valid ops: =, !=, >=, <=, >, <, ilike, not ilike. "
        "If user includes ranges like '>= 0.2', use the correct op. "
        "If you cannot extract structured filters, put the full query in text_query."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "temperature": 0.1,
    }
    headers = {
        "Authorization": "Bearer %s" % api_key,
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=25,
    )
    response.raise_for_status()
    data = response.json()
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return _extract_json(content), content

class MtrModule(http.Controller):
    @http.route('/mtr_module/mtr_module/', auth='public')
    def index(self, **kw):
        return "Hello, world"

    @http.route('/mtr_module/mtr_module/objects/', auth='public')
    def list(self, **kw):
        return http.request.render('mtr_module.listing', {
            'root': '/mtr_module/mtr_module',
            'objects': http.request.env['mtr_module.mtr_module'].search([]),
        })

    @http.route('/mtr_module/mtr_module/objects/<model("mtr_module.mtr_module"):obj>/', auth='public')
    def object(self, obj, **kw):
        return http.request.render('mtr_module.object', {
            'object': obj
        })


class MtrChatbotController(http.Controller):
    @http.route("/mtr_module/mtr_chatbot", type="json", auth="user")
    def mtr_chatbot(self, message=None, debug_llm=False):
        if not message:
            return {"error": _("Please enter a question.")}

        env = request.env
        text = (message or "").strip()

        # Match command: "match <spec>" / "run match for <spec>" / "find plates for <spec>"
        lowered = text.lower()
        match_prefixes = ["match ", "run match ", "run match for ", "find plates for ", "find match for "]
        for prefix in match_prefixes:
            if lowered.startswith(prefix):
                spec_name = text[len(prefix):].strip()
                return _run_spec_match(env, spec_name)
        if lowered.startswith("match:"):
            spec_name = text.split(":", 1)[1].strip()
            return _run_spec_match(env, spec_name)

        params = env["ir.config_parameter"].sudo()
        api_key = params.get_param("mtr_module.openai_api_key")
        model = params.get_param("mtr_module.openai_model") or "gpt-4o-mini"

        if not api_key:
            return {
                "error": _(
                    "OpenAI API key is not configured. "
                    "Set system parameter mtr_module.openai_api_key."
                )
            }

        parsed = None
        raw_llm = None
        try:
            parsed, raw_llm = _call_openai_parser(message, api_key, model)
        except Exception as exc:
            _logger.warning("OpenAI parse failed: %s", exc)

        parsed = parsed or {"filters": [], "text_query": message, "limit": 20}
        filters = parsed.get("filters") or []
        text_query = (parsed.get("text_query") or "").strip()
        if text_query.lower() in ("optional", "none", "null"):
            text_query = ""
        limit = parsed.get("limit") or 20
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 50))

        domain = _build_filters_domain(filters)
        if not domain:
            domain = _build_text_domain(text_query)
        else:
            text_domain = _build_text_domain(text_query)
            if text_domain:
                domain = domain + text_domain

        report = env["mtr.inventory.join.report"]
        fields = [
            "id",
            "join_status",
            "inv_lot_number",
            "inv_item_no",
            "inv_description",
            "inv_heat_number",
            "inv_slab_number",
            "inv_posting_date",
            "mtr_id",
            "mtr_heat_number",
            "mtr_batch_number",
            "mtr_grade",
            "mtr_manufacturer",
            "mtr_certificate_number",
            "mtr_certificate_date",
            "mtr_c",
            "mtr_mn",
            "mtr_yield_strength",
            "mtr_tensile_strength",
        ]
        results = report.search_read(domain, fields=fields, limit=limit)
        for row in results:
            row["join_id"] = row.get("id")

        source_label = "Join Report"

        if not results:
            mtr_domain = _build_mtr_filters_domain(filters)
            if not mtr_domain:
                mtr_domain = _build_mtr_text_domain(text_query)
            else:
                mtr_text_domain = _build_mtr_text_domain(text_query)
                if mtr_text_domain:
                    mtr_domain = mtr_domain + mtr_text_domain

            if mtr_domain:
                mtr_fields = [
                    "id",
                    "heat_number",
                    "batch_number",
                    "grade",
                    "manufacturer",
                    "certificate_number",
                    "certificate_date",
                    "country_of_melt",
                    "country_of_manufacture",
                    "c_element",
                    "mn_element",
                    "si_element",
                    "p_element",
                    "s_element",
                    "cu_element",
                    "ni_element",
                    "cr_element",
                    "mo_element",
                    "n_element",
                    "yield_strength",
                    "tensile_strength",
                    "elongation",
                    "reduction_area",
                    "hardness",
                    "impact_test_temp",
                    "impact_coupon_size",
                    "impact_specimen_1",
                    "impact_specimen_2",
                    "impact_specimen_3",
                    "impact_average",
                ]
                mtr_results = env["mtr.data"].search_read(
                    mtr_domain, fields=mtr_fields, limit=limit
                )
                results = []
                for row in mtr_results:
                    results.append({
                        "join_id": None,
                        "join_status": "MTR only",
                        "mtr_id": row.get("id"),
                        "mtr_heat_number": row.get("heat_number"),
                        "mtr_batch_number": row.get("batch_number"),
                        "mtr_grade": row.get("grade"),
                        "mtr_manufacturer": row.get("manufacturer"),
                        "mtr_certificate_number": row.get("certificate_number"),
                        "mtr_certificate_date": row.get("certificate_date"),
                        "mtr_c": row.get("c_element"),
                        "mtr_mn": row.get("mn_element"),
                        "mtr_si": row.get("si_element"),
                        "mtr_p": row.get("p_element"),
                        "mtr_s": row.get("s_element"),
                        "mtr_cu": row.get("cu_element"),
                        "mtr_ni": row.get("ni_element"),
                        "mtr_cr": row.get("cr_element"),
                        "mtr_mo": row.get("mo_element"),
                        "mtr_n": row.get("n_element"),
                        "mtr_yield_strength": row.get("yield_strength"),
                        "mtr_tensile_strength": row.get("tensile_strength"),
                        "mtr_elongation": row.get("elongation"),
                        "mtr_reduction_area": row.get("reduction_area"),
                        "mtr_hardness": row.get("hardness"),
                        "mtr_impact_test_temp": row.get("impact_test_temp"),
                        "mtr_impact_coupon_size": row.get("impact_coupon_size"),
                        "mtr_impact_specimen_1": row.get("impact_specimen_1"),
                        "mtr_impact_specimen_2": row.get("impact_specimen_2"),
                        "mtr_impact_specimen_3": row.get("impact_specimen_3"),
                        "mtr_impact_average": row.get("impact_average"),
                        "mtr_country_of_melt": row.get("country_of_melt"),
                        "mtr_country_of_manufacture": row.get("country_of_manufacture"),
                    })
                source_label = "MTR Records"

        answer = _(
            "Found %(count)s result(s) in %(source)s. Showing the top %(limit)s."
        ) % {"count": len(results), "limit": limit, "source": source_label}

        response = {
            "answer": answer,
            "results": results,
            "filters": filters,
            "text_query": text_query,
        }
        if debug_llm:
            response["debug_llm"] = raw_llm or ""
        return response

    @http.route("/mtr_module/spec_name", type="json", auth="user")
    def spec_name(self, spec_id=None):
        if not spec_id:
            return {"error": "missing_spec_id"}
        try:
            spec_id = int(spec_id)
        except Exception:
            return {"error": "invalid_spec_id"}
        spec = request.env["mtr.specification"].sudo().search([("id", "=", spec_id)], limit=1)
        if not spec:
            return {"error": "not_found"}
        return {"name": spec.name or ""}

    @http.route("/mtr_module/last_spec", type="json", auth="user")
    def last_spec(self):
        key = "mtr_module.last_spec_id.%s" % request.env.user.id
        spec_id = request.env["ir.config_parameter"].sudo().get_param(key) or ""
        try:
            spec_id_int = int(spec_id)
        except Exception:
            return {"error": "missing"}
        spec = request.env["mtr.specification"].sudo().search([("id", "=", spec_id_int)], limit=1)
        if not spec:
            return {"error": "missing"}
        return {"id": spec.id, "name": spec.name or ""}


def _run_spec_match(env, spec_name=None, spec_id=None):
    spec = None
    if spec_id:
        spec = env["mtr.specification"].search([("id", "=", spec_id)], limit=1)
    if not spec and spec_name:
        spec = env["mtr.specification"].search([("name", "ilike", spec_name)], limit=1)
    if not spec:
        return {
            "answer": _("Spec not found: %(name)s") % {"name": spec_name},
            "results": [],
        }

    wizard = env["mtr.spec.match.wizard"].create({"spec_id": spec.id})
    try:
        wizard.action_run_match()
    except Exception as exc:
        msg = str(exc)
        if "No data to match" in msg:
            return {
                "answer": _("No inventory with weight > 0."),
                "results": [],
            }
        return {
            "answer": _("No matches."),
            "results": [],
        }

    results = wizard.result_ids
    if not results:
        return {
            "answer": _("No matches."),
            "results": [],
        }

    rows = []
    join_report = env["mtr.inventory.join.report"]
    for row in results:
        join = join_report.search([
            ("mtr_id", "=", row.mtr_id.id),
            ("inv_lot_number", "=", row.inventory_id.lot_number),
        ], limit=1)
        rows.append({
            "mtr_id": row.mtr_id.id,
            "inventory_id": row.inventory_id.id,
            "mtr_heat_number": row.mtr_id.heat_number,
            "mtr_grade": row.mtr_id.grade,
            "inv_lot_number": row.inventory_id.lot_number,
            "inv_heat_number": row.inventory_id.heat_number,
            "inv_item_no": row.inventory_id.item_no,
            "inv_dimensions": row.inventory_id.dimensions,
            "inv_weight": row.inventory_id.weight,
            "inv_location": row.inventory_id.location_code,
            "score": row.score,
            "missing_notes": row.missing_notes,
            "chem_status": row.chem_status,
            "mech_status": row.mech_status,
            "impact_status": row.impact_status,
            "ce_status": row.ce_status,
            "grade_match": row.grade_match,
            "near_miss": row.near_miss,
            "ce_value": row.ce_value,
            "ce_max": row.ce_max,
            "join_id": join.id if join else None,
        })

    top = results[:1]
    top_line = ""
    if top:
        t = top[0]
        top_line = _(
            "Top hit: %(heat)s / %(lot)s at %(score)s%%."
        ) % {
            "heat": t.mtr_id.heat_number or "",
            "lot": t.inventory_id.lot_number or "",
            "score": t.score,
        }
    answer = _(
        "Matches for %(spec)s: %(count)s. %(top)s"
    ) % {"spec": spec.name, "count": len(results), "top": top_line}

    return {"answer": answer, "results": rows}


class MtrSpecIngestController(http.Controller):
    @http.route("/mtr_module/spec_ingest", type="json", auth="public", csrf=False)
    def spec_ingest(self, payload=None, token=None):
        env = request.env
        params = env["ir.config_parameter"].sudo()
        expected = params.get_param("mtr_module.spec_ingest_token") or ""
        raw_payload = payload

        # Fallback: accept raw JSON body (n8n can POST array/object without JSON-RPC)
        if not raw_payload:
            try:
                raw_body = request.httprequest.get_data(cache=False, as_text=True) or ""
                raw_body = raw_body.strip()
                if raw_body:
                    parsed = json.loads(raw_body)
                    # If JSON-RPC style, unwrap params.payload
                    if isinstance(parsed, dict) and "params" in parsed and isinstance(parsed.get("params"), dict):
                        raw_payload = parsed["params"].get("payload") or parsed["params"].get("data") or parsed["params"]
                    else:
                        raw_payload = parsed
            except Exception:
                raw_payload = None

        # If list of items, take the first (n8n often posts [ {..} ])
        if isinstance(raw_payload, list):
            raw_payload = raw_payload[0] if raw_payload else None

        provided = token or (raw_payload or {}).get("token") or ""
        if expected and provided != expected:
            return {"error": "invalid_token"}

        if not raw_payload:
            return {"error": "missing_payload"}
        if (raw_payload or {}).get("source") == "odoo13_mtr_module" and not (raw_payload or {}).get("spec_id"):
            return {
                "error": "missing_spec_id",
                "payload_keys": list((raw_payload or {}).keys()),
            }

        spec = env["mtr.specification"].sudo().upsert_from_payload(raw_payload)
        return {"status": "ok", "spec_id": spec.get("id")}
