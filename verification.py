"""Offline verification. Never fetches arbitrary lead-supplied URLs or invents identity verification."""
import re
from datetime import datetime
from urllib.parse import urlparse

SENSITIVE = {'privacy_request', 'executable_link', 'prompt_injection'}

def verify(row, base, previous_rows):
    """Return (safe revised decision, evidence). No network requests / email sends."""
    record = {'checks': [], 'flags': list(base['flags']), 'status': 'completed', 'next_action': 'NONE', 'human_review_required': base['decision']=='ESCALATE'}
    result = dict(base)
    def check(name, finding, source='fixture', verified=False):
        record['checks'].append({'check':name, 'finding':finding, 'source':source, 'verified':verified})
    flags = set(base['flags'])
    mail = (row.get('email') or '').strip().lower()
    domain = mail.rpartition('@')[-1] if '@' in mail else ''
    site = urlparse((row.get('website') or '').strip()).hostname or ''
    check('identity', 'contact_email_present' if mail else 'contact_email_missing', verified=bool(mail and domain))
    if mail and site:
        check('email_website_domain', 'matching' if domain == site.removeprefix('www.') else 'different_domains_not_proof_of_fraud', verified=(domain == site.removeprefix('www.')))
    if 'invalid_timestamp' in flags:
        # Timestamp quality is independent of an otherwise complete sales inquiry.
        check('timestamp','invalid_timestamp_preserved_for_source_correction')
        essential = all((row.get(k) or '').strip() for k in ('email','company','message'))
        if essential:
            result.update(decision='NURTURE',reason='Marketing inquiry is actionable, but its invalid submission timestamp needs correction.',confidence=0.83,route='sales')
            record['next_action']='CORRECT_SOURCE_TIMESTAMP'; record['human_review_required']=False
        else:
            record['next_action']='VERIFY_REQUIRED_FIELDS'
    if 'regulated_sector' in flags:
        check('compliance','needs_prelaunch_compliance_approval')
        result.update(decision='NURTURE',reason='Relevant healthcare marketing request; hold campaign work until compliance approval.',confidence=.85,route='sales')
        record['next_action']='COMPLIANCE_APPROVAL_BEFORE_EXECUTION';record['human_review_required']=False
    if 'budget_scope_conflict' in flags:
        check('budget_conflict','structured_budget_not_reinterpreted_without_contact_confirmation')
        result.update(decision='NURTURE',reason='Enterprise request has a contradictory stated budget; request clarification before sales qualification.',confidence=.88,route='sales')
        record['next_action']='REQUEST_BUDGET_CONFIRMATION';record['human_review_required']=False
    if 'empty_message' in flags:
        check('intent','missing_project_requirements_cannot_be_inferred_from_budget')
        record['next_action']='REQUEST_PROJECT_REQUIREMENTS';record['human_review_required']=True
    if 'invalid_email' in flags:
        check('contact','no_submitter_email_available;public_company_address_is_not_identity_proof')
        record['next_action']='VERIFY_CONTACT_CHANNEL';record['human_review_required']=True
    if 'disposable_email' in flags or 'unverified_identity' in flags:
        check('identity','external_identity_not_verified_offline')
        record['next_action']='VERIFY_IDENTITY';record['human_review_required']=True
    if 'privacy_request' in flags:
        record['next_action']='ROUTE_PRIVACY_TEAM';record['human_review_required']=True
    if 'executable_link' in flags:
        record['next_action']='ROUTE_SECURITY_TEAM_NO_FETCH';record['human_review_required']=True
    if 'prompt_injection' in flags:
        check('input_integrity','adversarial_instructions_ignored')
        record['next_action']='SECURITY_FLAG_NO_EXECUTION';record['human_review_required']=False
    record['final_decision']=result['decision']
    return result, record
