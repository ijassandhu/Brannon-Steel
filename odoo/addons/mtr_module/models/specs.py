# -*- coding: utf-8 -*-
import math
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError


_ELEMENT_FIELD_MAP = {
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
    "v": "v_element",
}


def _round5(value):
    if value in (None, False, ""):
        return None
    try:
        return round(float(value), 5)
    except (TypeError, ValueError):
        return None


def _safe_float(value):
    if value in (None, False, ""):
        return None
    return _round5(value)


def _normalize_text(value):
    return (value or "").strip().lower()

def _clean_spec_name(value):
    s = (value or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _normalize_heat(value):
    s = (value or "").upper()
    s = re.sub(r"[^A-Z0-9]+", "", s)
    return s.strip()


def _split_equivalents(value):
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        items = []
        for v in value:
            items.extend(_split_equivalents(v))
        return items
    text = str(value)
    # Split on common separators: comma, semicolon, pipe, newline
    parts = re.split(r"[,\n;|]+", text)
    expanded = []
    for part in parts:
        p = part.strip()
        if not p:
            continue
        # Split on slash when it looks like dual specs (e.g., A182/A350)
        if "/" in p and re.search(r"[A-Z]\d", p.upper()):
            expanded.extend([s.strip() for s in p.split("/") if s.strip()])
        else:
            expanded.append(p)
    return expanded


def _normalize_grade(value):
    text = _normalize_text(value)
    if not text:
        return ""
    # Remove common boilerplate tokens to match "ASTM A36" with "A36"
    text = re.sub(r"\b(astm|asme|api|aisi|grade)\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_grade_tokens(value):
    """
    Extract comparable grade tokens from mixed/compound grade strings.
    Examples:
      "CSA G40.21 50W / ASTM A572 GR 50 TY 2" -> ["g4021 50w", "a572 gr 50", "a572 50"]
      "ALGOMA 100 (96) / ASTM A514 GR S" -> ["a514 gr s", "a514 s"]
    """
    if not value:
        return []
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = set()

    # Match ASTM/ASME/API/AISI Axxx forms (optionally with GR/Grade)
    for m in re.finditer(r"\b(?:ASTM|ASME|API|AISI)\s*(A\d{2,4}[A-Z]?)\b", text, re.IGNORECASE):
        code = m.group(1).upper()
        suffix = ""
        after = text[m.end(): m.end() + 30]
        g = re.search(r"\b(?:GR|GRADE)\s*([A-Z0-9]+(?:\s*\d+)?)\b", after, re.IGNORECASE)
        if g:
            suffix = g.group(1).strip()
        base = code.lower()
        if suffix:
            tokens.add(f"{base} gr {suffix.lower()}")
        # also add base without grade to allow loose matching (A572)
        tokens.add(base)

    # Match CSA G40.21 50W
    for m in re.finditer(r"\bCSA\s*G\s*40\.?21\s*([0-9]{2,3}\s*[A-Z]?)\b", text, re.IGNORECASE):
        grade = m.group(1).replace(" ", "").upper()
        tokens.add(f"g4021 {grade.lower()}")

    # Match plain A###, A###X, etc if present in text
    for m in re.finditer(r"\bA\d{2,4}[A-Z]?\b", text, re.IGNORECASE):
        tokens.add(m.group(0).lower())

    # Match standalone GR/Grade tokens with context e.g., "A514 GR S"
    # If no ASTM code captured, still try to keep "gr X" as a weak token
    if not tokens:
        for m in re.finditer(r"\b(?:GR|GRADE)\s*([A-Z0-9]+)\b", text, re.IGNORECASE):
            tokens.add(f"gr {m.group(1).lower()}")

    return list(tokens)


def _parse_first_number(text):
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return _round5(match.group(1))


def _parse_thickness(dimensions):
    if not dimensions:
        return None
    # Try to parse typical formats like "1.5 x 96 x 240" or "1-1/2 X 96".
    text = dimensions.replace("×", "x").replace("X", "x")
    parts = [p.strip() for p in text.split("x") if p.strip()]
    if parts:
        # First segment is usually thickness.
        first = parts[0]
        # Handle simple fraction like 1-1/2.
        if "-" in first and "/" in first:
            try:
                whole, frac = first.split("-", 1)
                num, den = frac.split("/", 1)
                return _round5(float(whole) + (float(num) / float(den)))
            except Exception:
                pass
        # Handle fraction like 1/2.
        if "/" in first:
            try:
                num, den = first.split("/", 1)
                return _round5(float(num) / float(den))
            except Exception:
                pass
        return _parse_first_number(first)
    return _parse_first_number(dimensions)


def _ksi_to_mpa(value):
    if value is None:
        return None
    return _round5(value * 6.89476)


def _mpa_to_ksi(value):
    if value is None:
        return None
    return _round5(value / 6.89476)


def _j_to_ftlb(value):
    if value is None:
        return None
    return _round5(value / 1.35582)


def _ftlb_to_j(value):
    if value is None:
        return None
    return _round5(value * 1.35582)


class MtrSpecification(models.Model):
    _name = "mtr.specification"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "MTR Specification"
    _rec_name = "name"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True)
    revision = fields.Char()
    customer = fields.Char()
    astm_equivalent = fields.Char(help="Comma-separated list, e.g., A572 Grade 50")
    effective_date = fields.Date()
    upload_date = fields.Date(default=fields.Date.today)
    status = fields.Selection([
        ("pending", "Pending"),
        ("active", "Active"),
        ("archived", "Archived"),
    ], default="active")

    requires_impact = fields.Boolean(default=False)
    requires_ce = fields.Boolean(default=False)
    ce_formula = fields.Text(default="CE = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15")

    chem_limit_ids = fields.One2many("mtr.spec.chem.limit", "spec_id", string="Chemistry Limits")
    mech_limit_ids = fields.One2many("mtr.spec.mech.limit", "spec_id", string="Mechanical Limits")
    impact_limit_ids = fields.One2many("mtr.spec.impact.limit", "spec_id", string="Impact Limits")
    condition_rule_ids = fields.One2many("mtr.spec.condition.rule", "spec_id", string="Conditional Rules")
    ce_threshold_ids = fields.One2many("mtr.spec.ce.threshold", "spec_id", string="CE Thresholds")

    notes = fields.Text()
    source_pdf = fields.Binary(string="Spec PDF")
    source_pdf_name = fields.Char(string="Spec PDF Name")

    def action_open_match_wizard(self):
        self.ensure_one()
        wizard = self.env["mtr.spec.match.wizard"].create({"spec_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Specification Match"),
            "res_model": "mtr.spec.match.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def action_open_chatbot_match(self):
        self.ensure_one()
        # Persist last spec for chatbot (per user) as a fallback when context is not passed
        key = "mtr_module.last_spec_id.%s" % self.env.user.id
        self.env["ir.config_parameter"].sudo().set_param(key, str(self.id))
        return {
            "type": "ir.actions.client",
            "tag": "mtr_module.mtr_chatbot_action",
            "name": _("MTR Chatbot"),
            "context": {
                "match_spec_id": self.id,
                "match_spec_name": self.name,
            },
            "params": {
                "match_spec_id": self.id,
                "match_spec_name": self.name,
            },
        }

    @api.model
    def upsert_from_payload(self, payload):
        if not isinstance(payload, dict):
            raise UserError(_("Payload must be a dictionary."))

        spec_id = payload.get("spec_id")
        if isinstance(spec_id, str) and spec_id.strip().isdigit():
            spec_id = int(spec_id.strip())
        spec_name = _clean_spec_name(payload.get("spec_name") or payload.get("name") or "")
        if not spec_id and not spec_name:
            raise UserError(_("spec_name or spec_id is required."))

        values = {
            "name": spec_name or payload.get("spec_code") or payload.get("spec"),
            "revision": payload.get("revision"),
            "customer": payload.get("customer"),
            "astm_equivalent": ", ".join(_split_equivalents(payload.get("astm_equivalent"))),
            "requires_impact": bool(payload.get("requires_impact")),
            "requires_ce": bool(payload.get("requires_ce")),
            "ce_formula": payload.get("ce_formula") or self._fields["ce_formula"].default(self),
            "notes": payload.get("notes"),
            "status": payload.get("status") or "active",
        }

        spec = None
        if spec_id:
            spec = self.search([("id", "=", spec_id)], limit=1)
            if not spec:
                raise UserError(_("spec_id %s not found. Pending record may not exist or wrong database.") % spec_id)
        if not spec and not spec_id and spec_name:
            domain = [("name", "ilike", spec_name)]
            if payload.get("revision"):
                domain.append(("revision", "=", payload.get("revision")))
            if payload.get("customer"):
                domain.append(("customer", "ilike", payload.get("customer")))
            spec = self.search(domain, limit=1)
            # Fallback: if spec_name contains comma, try first token
            if not spec and "," in spec_name:
                first = _clean_spec_name(spec_name.split(",")[0])
                if first:
                    domain = [("name", "ilike", first)]
                    if payload.get("revision"):
                        domain.append(("revision", "=", payload.get("revision")))
                    if payload.get("customer"):
                        domain.append(("customer", "ilike", payload.get("customer")))
                    spec = self.search(domain, limit=1)

        if spec:
            # If pending record, prefer AI spec_name to replace placeholder
            if spec.name and spec.name.upper().startswith("PENDING") and spec_name:
                values["name"] = spec_name
                values["status"] = "active"
            spec.write(values)
        else:
            spec = self.create(values)

        spec._replace_lines_from_payload(payload)
        return {"id": spec.id, "operation": "updated" if spec_id or spec_name else "created"}

    def _replace_lines_from_payload(self, payload):
        self.ensure_one()
        def _clear_lines(model):
            self.env[model].search([("spec_id", "=", self.id)]).unlink()

        _clear_lines("mtr.spec.chem.limit")
        _clear_lines("mtr.spec.mech.limit")
        _clear_lines("mtr.spec.impact.limit")
        _clear_lines("mtr.spec.condition.rule")
        _clear_lines("mtr.spec.ce.threshold")

        for line in payload.get("chem_limits") or []:
            raw_source = (line.get("source") or "table")
            source_norm = str(raw_source).strip().lower()
            if source_norm not in ("table", "footnote"):
                source_norm = "table"
            raw_element = (line.get("element") or "").strip().lower()
            element_alias = {
                "carbon": "c",
                "manganese": "mn",
                "silicon": "si",
                "phosphorus": "p",
                "sulfur": "s",
                "sulphur": "s",
                "copper": "cu",
                "nickel": "ni",
                "chromium": "cr",
                "molybdenum": "mo",
                "nitrogen": "n",
            }
            element = element_alias.get(raw_element, raw_element)
            allowed_elements = {"c", "mn", "si", "p", "s", "cu", "ni", "cr", "mo", "n"}
            if element not in allowed_elements:
                # Skip unsupported elements (e.g., Pb/lead)
                continue
            self.env["mtr.spec.chem.limit"].create({
                "spec_id": self.id,
                "element": element,
                "min_value": _safe_float(line.get("min")),
                "max_value": _safe_float(line.get("max")),
                "source": source_norm,
            })

        for line in payload.get("mech_limits") or []:
            raw_unit = (line.get("unit") or "ksi")
            unit_norm = str(raw_unit).strip().lower()
            if unit_norm in ("percent", "percentage", "%"):
                unit_norm = "%"
            elif unit_norm in ("mpa", "megapascal", "megapascals"):
                unit_norm = "mpa"
            elif unit_norm in ("ksi", "ks", "kpsi"):
                unit_norm = "ksi"
            elif unit_norm in ("bhn", "brinell"):
                unit_norm = "bhn"
            else:
                # default to ksi if unknown (for compatibility)
                unit_norm = "ksi"
            raw_prop = (line.get("property") or "").strip().lower()
            # Normalize common AI/property variants like "tensile_min" or "yield_strength"
            raw_prop = raw_prop.replace("-", "_").replace(" ", "_")
            for suffix in ("_min", "_max", "_minimum", "_maximum"):
                if raw_prop.endswith(suffix):
                    raw_prop = raw_prop[: -len(suffix)]
            raw_prop = raw_prop.strip("_")
            if raw_prop.startswith("elongation"):
                prop_norm = "elongation"
            elif "tensile" in raw_prop or raw_prop in ("uts", "ultimate"):
                prop_norm = "tensile"
            elif "yield" in raw_prop or raw_prop in ("ys", "yieldstrength", "yield_strength"):
                prop_norm = "yield"
            elif "hardness" in raw_prop or raw_prop in ("bhn", "brinell"):
                prop_norm = "hardness"
            elif raw_prop in ("yield", "tensile", "hardness", "elongation"):
                prop_norm = raw_prop
            else:
                prop_norm = raw_prop or "yield"
            raw_min = line.get("min")
            raw_max = line.get("max")
            min_value = _safe_float(raw_min)
            max_value = _safe_float(raw_max)
            # Treat 0 as "not provided" when paired with a real min (common AI output)
            def _is_zeroish(v):
                return v in (0, 0.0, "0", "0.0")
            if (raw_max is None or raw_max == "" or _is_zeroish(raw_max)) and (raw_min not in (None, "") and not _is_zeroish(raw_min)):
                max_value = None
            if (raw_min is None or raw_min == "" or _is_zeroish(raw_min)) and (raw_max not in (None, "") and not _is_zeroish(raw_max)):
                min_value = None
            self.env["mtr.spec.mech.limit"].create({
                "spec_id": self.id,
                "property": prop_norm,
                "min_value": min_value,
                "max_value": max_value,
                "unit": unit_norm,
                "specimen_size": line.get("specimen_size"),
            })

        for line in payload.get("impact_limits") or []:
            raw_unit = (line.get("unit") or "j")
            unit_norm = str(raw_unit).strip().lower()
            if unit_norm in ("ft-lb", "ft-lbs", "ftlb", "ftlbs", "ft lb", "ft lbs"):
                unit_norm = "ftlb"
            elif unit_norm in ("j", "joule", "joules"):
                unit_norm = "j"
            else:
                unit_norm = "j"
            self.env["mtr.spec.impact.limit"].create({
                "spec_id": self.id,
                "temperature": _safe_float(line.get("temperature")),
                "coupon_size": line.get("coupon_size"),
                "min_average": _safe_float(line.get("min_average")),
                "min_individual": _safe_float(line.get("min_individual")),
                "unit": unit_norm,
                "min_readings": int(line.get("min_readings") or 3),
                "orientation": line.get("orientation"),
            })

        for line in payload.get("condition_rules") or []:
            target = (line.get("target_element") or "").lower().strip()
            cond = (line.get("condition_element") or "").lower().strip()
            allowed_elements = {"c", "mn", "si", "p", "s", "cu", "ni", "cr", "mo", "n", "v"}
            element_alias = {
                "carbon": "c",
                "manganese": "mn",
                "silicon": "si",
                "phosphorus": "p",
                "sulfur": "s",
                "sulphur": "s",
                "copper": "cu",
                "nickel": "ni",
                "chromium": "cr",
                "molybdenum": "mo",
                "nitrogen": "n",
                "vanadium": "v",
            }
            target = element_alias.get(target, target)
            cond = element_alias.get(cond, cond)
            if target not in allowed_elements or cond not in allowed_elements:
                # Skip unsupported condition rules (e.g., thickness-based rules)
                continue
            self.env["mtr.spec.condition.rule"].create({
                "spec_id": self.id,
                "target_element": target,
                "condition_element": cond,
                "condition_type": line.get("condition_type"),
                "condition_threshold": _safe_float(line.get("condition_threshold")),
                "target_adjustment": _safe_float(line.get("target_adjustment")),
                "target_new_max": _safe_float(line.get("target_new_max")),
                "description": line.get("description"),
            })

        for line in payload.get("ce_thresholds") or []:
            self.env["mtr.spec.ce.threshold"].create({
                "spec_id": self.id,
                "thickness_min": _safe_float(line.get("thickness_min")),
                "thickness_max": _safe_float(line.get("thickness_max")),
                "max_ce": _safe_float(line.get("max_ce")),
            })

    def _get_conditioned_max(self, element_key, base_max, mtr_values):
        if base_max is None:
            base_max_value = None
        else:
            base_max_value = _round5(base_max)

        adjusted = base_max_value
        rules = self.condition_rule_ids.filtered(lambda r: r.target_element == element_key)
        for rule in rules:
            cond_value = mtr_values.get(rule.condition_element)
            if cond_value is None:
                continue
            cond_limit = self.chem_limit_ids.filtered(
                lambda l: l.element == rule.condition_element
            )
            cond_baseline = cond_limit[:1].max_value if cond_limit else None
            step = rule.condition_threshold or 0.0
            target_adjustment = rule.target_adjustment or 0.0
            if rule.condition_type == "below":
                if cond_value <= (rule.condition_threshold or cond_value):
                    adjusted = rule.target_new_max or (
                        (base_max_value or 0.0) + target_adjustment
                    )
            elif rule.condition_type == "above":
                if cond_value >= (rule.condition_threshold or cond_value):
                    adjusted = rule.target_new_max or (
                        (base_max_value or 0.0) + target_adjustment
                    )
            elif rule.condition_type in ("decrease_by", "increase_by"):
                baseline = cond_baseline
                if baseline is None or step <= 0:
                    continue
                if rule.condition_type == "decrease_by" and cond_value < baseline:
                    steps = math.floor((baseline - cond_value) / step)
                    adjusted = (base_max_value or 0.0) + (steps * target_adjustment)
                if rule.condition_type == "increase_by" and cond_value > baseline:
                    steps = math.floor((cond_value - baseline) / step)
                    adjusted = (base_max_value or 0.0) + (steps * target_adjustment)
            if rule.target_new_max and adjusted is not None:
                adjusted = min(adjusted, rule.target_new_max)

        return _round5(adjusted)

    def _compute_ce(self, mtr_values):
        required = ["c", "mn", "cr", "mo", "ni", "cu"]
        for key in required:
            if mtr_values.get(key) is None:
                return None
        c = mtr_values.get("c") or 0.0
        mn = mtr_values.get("mn") or 0.0
        cr = mtr_values.get("cr") or 0.0
        mo = mtr_values.get("mo") or 0.0
        v = mtr_values.get("v") or 0.0
        ni = mtr_values.get("ni") or 0.0
        cu = mtr_values.get("cu") or 0.0
        return _round5(c + (mn / 6.0) + ((cr + mo + v) / 5.0) + ((ni + cu) / 15.0))


class MtrSpecChemLimit(models.Model):
    _name = "mtr.spec.chem.limit"
    _description = "Spec Chemistry Limit"
    _order = "element asc"

    spec_id = fields.Many2one("mtr.specification", required=True, ondelete="cascade")
    element = fields.Selection(
        [("c", "C"), ("mn", "Mn"), ("si", "Si"), ("p", "P"), ("s", "S"),
         ("cu", "Cu"), ("ni", "Ni"), ("cr", "Cr"), ("mo", "Mo"), ("n", "N"), ("v", "V")],
        required=True,
    )
    min_value = fields.Float(digits=(16, 5))
    max_value = fields.Float(digits=(16, 5))
    source = fields.Selection([( "table", "Table"), ("footnote", "Footnote")], default="table")


class MtrSpecConditionRule(models.Model):
    _name = "mtr.spec.condition.rule"
    _description = "Spec Conditional Rule"
    _order = "id asc"

    spec_id = fields.Many2one("mtr.specification", required=True, ondelete="cascade")
    target_element = fields.Selection(
        [("c", "C"), ("mn", "Mn"), ("si", "Si"), ("p", "P"), ("s", "S"),
         ("cu", "Cu"), ("ni", "Ni"), ("cr", "Cr"), ("mo", "Mo"), ("n", "N"), ("v", "V")],
        required=True,
    )
    condition_element = fields.Selection(
        [("c", "C"), ("mn", "Mn"), ("si", "Si"), ("p", "P"), ("s", "S"),
         ("cu", "Cu"), ("ni", "Ni"), ("cr", "Cr"), ("mo", "Mo"), ("n", "N"), ("v", "V")],
        required=True,
    )
    condition_type = fields.Selection(
        [("decrease_by", "Decrease By"), ("increase_by", "Increase By"),
         ("below", "Below"), ("above", "Above")],
        required=True,
    )
    condition_threshold = fields.Float(digits=(16, 5), help="Step size or threshold based on condition type.")
    target_adjustment = fields.Float(digits=(16, 5), help="Adjustment per step or flat adjustment.")
    target_new_max = fields.Float(digits=(16, 5), help="Absolute ceiling for the target element.")
    description = fields.Text()


class MtrSpecMechLimit(models.Model):
    _name = "mtr.spec.mech.limit"
    _description = "Spec Mechanical Limit"
    _order = "property asc"

    spec_id = fields.Many2one("mtr.specification", required=True, ondelete="cascade")
    property = fields.Selection(
        [
            ("yield", "Yield"),
            ("tensile", "Tensile"),
            ("elongation", "Elongation"),
            ("hardness", "Hardness"),
        ],
        required=True,
    )
    min_value = fields.Float(digits=(16, 5))
    max_value = fields.Float(digits=(16, 5))
    unit = fields.Selection(
        [("ksi", "KSI"), ("mpa", "MPa"), ("%", "%"), ("bhn", "BHN")],
        default="ksi",
    )
    specimen_size = fields.Char()


class MtrSpecImpactLimit(models.Model):
    _name = "mtr.spec.impact.limit"
    _description = "Spec Impact Limit"
    _order = "id asc"

    spec_id = fields.Many2one("mtr.specification", required=True, ondelete="cascade")
    temperature = fields.Float(digits=(16, 5), help="Requirement temperature (C).")
    coupon_size = fields.Char()
    min_average = fields.Float(digits=(16, 5))
    min_individual = fields.Float(digits=(16, 5))
    unit = fields.Selection([("j", "J"), ("ftlb", "ft-lbs")], default="j")
    min_readings = fields.Integer(default=3)
    orientation = fields.Char()


class MtrSpecCeThreshold(models.Model):
    _name = "mtr.spec.ce.threshold"
    _description = "Spec Carbon Equivalency Threshold"

    spec_id = fields.Many2one("mtr.specification", required=True, ondelete="cascade")
    thickness_min = fields.Float(digits=(16, 5), help="Minimum thickness (inches).")
    thickness_max = fields.Float(digits=(16, 5), help="Maximum thickness (inches).")
    max_ce = fields.Float(digits=(16, 5), required=True)


class MtrSpecUploadWizard(models.TransientModel):
    _name = "mtr.spec.upload.wizard"
    _description = "Spec PDF Upload Wizard"

    file_data = fields.Binary(required=False)
    file_name = fields.Char(required=False)
    file_ids = fields.Many2many(
        "ir.attachment",
        "mtr_spec_upload_wizard_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Spec Files",
        help="Upload one or more spec PDFs.",
    )
    spec_name = fields.Char(required=False)
    revision = fields.Char()
    customer = fields.Char()
    webhook_url = fields.Char(
        default=lambda self: self.env["ir.config_parameter"].sudo().get_param(
            "mtr_module.spec_n8n_webhook_url"
        ) or "https://innovation.eoxs.com/webhook/spec-upload"
    )

    def action_submit_spec(self):
        self.ensure_one()
        if not self.webhook_url:
            raise UserError(_("Please configure spec webhook URL first."))

        files = []
        for attachment in self.file_ids:
            if attachment.datas:
                files.append({
                    "file_name": attachment.name or "spec.pdf",
                    "file_data": attachment.datas,
                })
        if not files and self.file_data:
            files.append({
                "file_name": self.file_name or "spec.pdf",
                "file_data": self.file_data,
            })
        if not files:
            raise UserError(_("Please upload at least one file."))

        self.env["ir.config_parameter"].sudo().set_param(
            "mtr_module.spec_n8n_webhook_url", self.webhook_url
        )

        first_spec = None
        for idx, f in enumerate(files):
            file_name = f["file_name"]
            file_data = f["file_data"]

            pending_name = self.spec_name if (self.spec_name and len(files) == 1) else ""
            if not pending_name:
                stamp = fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                base = file_name or "Spec PDF"
                pending_name = f"PENDING {base} {stamp}"

            spec = self.env["mtr.specification"].with_context(mail_create_nolog=True).create({
                "name": pending_name,
                "revision": self.revision,
                "customer": self.customer,
                "status": "pending" if not self.spec_name else "active",
            })
            if not first_spec:
                first_spec = spec

            attachment = self.env["ir.attachment"].create(
                {
                    "name": file_name or "Spec.pdf",
                    "res_model": "mtr.specification",
                    "res_id": spec.id,
                    "type": "binary",
                    "datas": file_data,
                    "mimetype": "application/pdf",
                }
            )
            spec.sudo().message_post(
                body="Spec PDF uploaded",
                attachment_ids=[attachment.id],
                message_type="comment",
                subtype_id=self.env.ref("mail.mt_note").id,
            )

            payload = {
                "source": "odoo13_mtr_module",
                "spec_id": spec.id,
                "spec_name": spec.name,
                "file_name": file_name,
                "file_data": file_data.decode("utf-8") if isinstance(file_data, bytes) else file_data,
                "db_name": self.env.cr.dbname,
            }

            # Send to n8n for parsing.
            self.env["mtr.spec.upload.wizard"]._post_payload(self.webhook_url, payload)

        if not first_spec:
            raise UserError(_("No specs were created."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Specification"),
            "res_model": "mtr.specification",
            "view_mode": "form",
            "res_id": first_spec.id,
        }

    @api.model
    def _post_payload(self, webhook_url, payload):
        from .models import _post_payload_to_n8n  # reuse helper
        _post_payload_to_n8n(webhook_url, payload)


class MtrSpecMatchWizard(models.TransientModel):
    _name = "mtr.spec.match.wizard"
    _description = "Specification Match Wizard"

    spec_id = fields.Many2one("mtr.specification", required=True)
    result_ids = fields.One2many("mtr.spec.match.result", "wizard_id", string="Results")

    def action_run_match(self):
        return self._run_match_engine(chem_only=False)

    def _run_match_engine(self, chem_only=False):
        self.ensure_one()
        self.result_ids.unlink()
        spec = self.spec_id

        mtr_records = self.env["mtr.data"].search([])
        inventory_records = self.env["inventory.record"].search([])
        if not mtr_records or not inventory_records:
            raise UserError(
                "No data to match. MTR records: %s, Inventory records (weight>0): %s"
                % (len(mtr_records), len(inventory_records))
            )
        inventory_by_heat = {}
        for inv in inventory_records:
            key = _normalize_heat(inv.heat_number)
            if not key:
                continue
            inventory_by_heat.setdefault(key, []).append(inv)

        equivalents = [spec.name] + _split_equivalents(spec.astm_equivalent)
        equivalents = [_normalize_grade(e) for e in equivalents if e]
        equivalent_tokens = set()
        for e in equivalents:
            for tok in _extract_grade_tokens(e):
                equivalent_tokens.add(_normalize_grade(tok))

        created = 0
        for mtr in mtr_records:
            mtr_values = {}
            for key, field in _ELEMENT_FIELD_MAP.items():
                mtr_values[key] = _safe_float(getattr(mtr, field, None))

            grade_value = _normalize_grade(mtr.grade)
            grade_tokens = _extract_grade_tokens(mtr.grade)
            grade_tokens = [_normalize_grade(t) for t in grade_tokens]
            grade_match = False
            if equivalents:
                if grade_value in equivalents:
                    grade_match = True
                elif equivalent_tokens and any(t in equivalent_tokens for t in grade_tokens):
                    grade_match = True

            chem_status, chem_missing, chem_near = self._check_chemistry(spec, mtr_values)
            if chem_only:
                mech_status, mech_missing, mech_near = ("n/a", False, False)
                impact_status, impact_missing = ("n/a", False)
            else:
                mech_status, mech_missing, mech_near = self._check_mechanical(spec, mtr)
                impact_status, impact_missing = self._check_impact(spec, mtr)

            # Inventory join per heat
            inv_list = inventory_by_heat.get(_normalize_heat(mtr.heat_number)) or []
            if not inv_list:
                continue

            for inv in inv_list:
                if chem_only:
                    ce_status, ce_missing, ce_value, ce_max = ("n/a", False, None, None)
                else:
                    ce_status, ce_missing, ce_value, ce_max = self._check_ce(spec, mtr_values, inv)

                hard_fail = any(status == "fail" for status in [chem_status, mech_status, impact_status, ce_status])
                missing = any([chem_missing, mech_missing, impact_missing, ce_missing])
                near_miss = bool(chem_near or mech_near)

                score = 0
                if chem_only:
                    if hard_fail:
                        score = 40
                    elif missing:
                        score = 60
                    else:
                        score = 80 if grade_match else 60
                else:
                    if hard_fail:
                        score = 40
                    elif missing:
                        score = 60
                    else:
                        score = 100 if grade_match else 80
                    if near_miss and not hard_fail:
                        score = 60

                if score < 50:
                    continue

                notes = []
                if not grade_match:
                    notes.append("Grade not on MTR")
                if chem_missing:
                    notes.append("Missing chemistry")
                if mech_missing:
                    notes.append("Missing mechanical")
                if not chem_only:
                    if impact_missing:
                        notes.append("Missing impact")
                    if ce_missing and (spec.requires_ce or spec.ce_threshold_ids):
                        notes.append("CE not calculable")

                self.env["mtr.spec.match.result"].create({
                    "wizard_id": self.id,
                    "mtr_id": mtr.id,
                    "inventory_id": inv.id,
                    "score": score,
                    "grade_match": grade_match,
                    "near_miss": near_miss,
                    "chem_status": chem_status,
                    "mech_status": mech_status,
                    "impact_status": impact_status if (not chem_only and spec.requires_impact) else "n/a",
                    "ce_status": ce_status if (not chem_only and (spec.requires_ce or spec.ce_threshold_ids)) else "n/a",
                    "ce_value": ce_value,
                    "ce_max": ce_max,
                    "missing_notes": "; ".join(notes),
                })
                created += 1

        if created == 0:
            raise UserError(
                "No matches found. Check heat numbers, inventory (weight>0), and spec limits."
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Match Results"),
            "res_model": "mtr.spec.match.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def _check_chemistry(self, spec, mtr_values):
        near_miss = False
        missing = False
        for limit in spec.chem_limit_ids:
            value = mtr_values.get(limit.element)
            if value is None:
                missing = True
                continue
            max_allowed = spec._get_conditioned_max(limit.element, limit.max_value, mtr_values)
            if limit.min_value not in (None, False) and value < limit.min_value:
                return "fail", missing, near_miss
            if max_allowed is not None and value > max_allowed:
                return "fail", missing, near_miss
            if limit.min_value not in (None, False) and value <= (limit.min_value * 1.05):
                near_miss = True
            if max_allowed is not None and value >= (max_allowed * 0.95):
                near_miss = True
        return "pass", missing, near_miss

    def _check_mechanical(self, spec, mtr):
        near_miss = False
        missing = False
        for line in spec.mech_limit_ids:
            if line.property == "yield":
                value = mtr.yield_strength
            elif line.property == "tensile":
                value = mtr.tensile_strength
            elif line.property == "hardness":
                value = mtr.hardness
            else:
                value = mtr.elongation

            value = _safe_float(value)
            if value is None:
                missing = True
                continue

            min_value = line.min_value
            max_value = line.max_value
            # Some rows store 0.0 instead of NULL; treat 0 as "not provided"
            if (max_value in (0, 0.0)) and (min_value not in (None, 0, 0.0)):
                max_value = None
            if (min_value in (0, 0.0)) and (max_value not in (None, 0, 0.0)):
                min_value = None
            if line.unit == "mpa":
                min_value = _mpa_to_ksi(min_value) if min_value is not None else None
                max_value = _mpa_to_ksi(max_value) if max_value is not None else None

            if min_value is not None and value < min_value:
                return "fail", missing, near_miss
            if max_value is not None and value > max_value:
                return "fail", missing, near_miss

            if min_value is not None and value <= (min_value * 1.05):
                near_miss = True
            if max_value is not None and value >= (max_value * 0.95):
                near_miss = True

        return "pass", missing, near_miss

    def _check_impact(self, spec, mtr):
        if not spec.requires_impact:
            return "n/a", False
        if not spec.impact_limit_ids:
            return "missing", True

        # Match by coupon size when possible; otherwise use first line.
        line = None
        if mtr.impact_coupon_size:
            coupon = _normalize_text(mtr.impact_coupon_size)
            for candidate in spec.impact_limit_ids:
                if _normalize_text(candidate.coupon_size) == coupon:
                    line = candidate
                    break
        if not line:
            line = spec.impact_limit_ids[:1]
        if not line:
            return "missing", True

        temp = _safe_float(mtr.impact_test_temp)
        if temp is None:
            return "missing", True
        if line.temperature is not None and temp > line.temperature:
            return "fail", False

        specimens = [
            _safe_float(mtr.impact_specimen_1),
            _safe_float(mtr.impact_specimen_2),
            _safe_float(mtr.impact_specimen_3),
        ]
        specimens = [v for v in specimens if v is not None]
        if len(specimens) < (line.min_readings or 3):
            return "missing", True

        avg = _safe_float(mtr.impact_average)
        if avg is None and specimens:
            avg = _round5(sum(specimens) / len(specimens))

        min_avg = line.min_average
        min_individual = line.min_individual
        if line.unit == "ftlb":
            min_avg = _ftlb_to_j(min_avg) if min_avg is not None else None
            min_individual = _ftlb_to_j(min_individual) if min_individual is not None else None

        if min_avg is not None and avg is not None and avg < min_avg:
            return "fail", False
        if min_individual is not None:
            for value in specimens:
                if value < min_individual:
                    return "fail", False

        return "pass", False

    def _check_ce(self, spec, mtr_values, inventory):
        if not spec.requires_ce and not spec.ce_threshold_ids:
            return "n/a", False, None, None
        ce_value = spec._compute_ce(mtr_values)
        if ce_value is None:
            return "missing", True, None, None
        thickness = _parse_thickness(inventory.dimensions)
        max_ce = None
        thresholds = spec.ce_threshold_ids.sorted(lambda t: (t.thickness_min or 0.0, t.thickness_max or 9999))
        for threshold in thresholds:
            if threshold.thickness_min and thickness is not None and thickness < threshold.thickness_min:
                continue
            if threshold.thickness_max and thickness is not None and thickness > threshold.thickness_max:
                continue
            max_ce = threshold.max_ce
            break
        if max_ce is None:
            return "missing", True, ce_value, None
        if ce_value > max_ce:
            return "fail", False, ce_value, max_ce
        return "pass", False, ce_value, max_ce


class MtrSpecMatchResult(models.TransientModel):
    _name = "mtr.spec.match.result"
    _description = "Spec Match Result"
    _order = "score desc, id asc"

    wizard_id = fields.Many2one("mtr.spec.match.wizard", required=True, ondelete="cascade")
    mtr_id = fields.Many2one("mtr.data", required=True)
    inventory_id = fields.Many2one("inventory.record", required=True)

    score = fields.Integer()
    grade_match = fields.Boolean()
    near_miss = fields.Boolean()

    chem_status = fields.Selection([("pass", "Pass"), ("fail", "Fail"), ("missing", "Missing")])
    mech_status = fields.Selection([("pass", "Pass"), ("fail", "Fail"), ("missing", "Missing")])
    impact_status = fields.Selection([("pass", "Pass"), ("fail", "Fail"), ("missing", "Missing"), ("n/a", "N/A")])
    ce_status = fields.Selection([("pass", "Pass"), ("fail", "Fail"), ("missing", "Missing"), ("n/a", "N/A")])

    ce_value = fields.Float(digits=(16, 5))
    ce_max = fields.Float(digits=(16, 5))
    missing_notes = fields.Char()

    heat_number = fields.Char(related="mtr_id.heat_number", readonly=True)
    grade = fields.Char(related="mtr_id.grade", readonly=True)
    lot_number = fields.Char(related="inventory_id.lot_number", readonly=True)
    dimensions = fields.Char(related="inventory_id.dimensions", readonly=True)
    weight = fields.Float(digits=(16, 5), related="inventory_id.weight", readonly=True)
    location = fields.Char(related="inventory_id.location_code", readonly=True)
