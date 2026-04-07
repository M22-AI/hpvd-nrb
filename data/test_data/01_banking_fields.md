# Banking Field Inventory

This document summarizes all fields currently recognized by the banking plugin, based on `plugins/banking/spec.py`. In practice, banking fields include transaction identifiers, lender and beneficiary information, collateral details, financing details, supporting documents, risk events, recovery, claims, exposure, legal declarations, credit bureau data, commissions, and transaction changes such as suspension and consolidation. This list is a raw field dictionary: it does not yet distinguish between fields that are merely informative, those required for v1 coverage, and those directly used by v3 rules.

The fields are:

## 1. Operational and Program Identity

- `operation_id`
- `practice_id`
- `fund_code`
- `fund_section`
- `guarantee_type`
- `guarantee_subtype`
- `process_type`
- `aid_regime`
- `temporary_framework_flag`
- `temporary_framework_type`

## 2. Lender Information

- `lender_name`
- `lender_code`
- `lender_branch`
- `lender_country`

## 3. Beneficiary / Company Information

- `beneficiary_name`
- `beneficiary_vat`
- `beneficiary_tax_code`
- `legal_form`
- `ateco_code`
- `sector`
- `company_size`
- `foundation_date`
- `activity_start_date`
- `company_status`

## 4. Guarantee Information

- `guarantee_issue_date`
- `guarantee_expiry_date`
- `guarantee_percentage`
- `guarantee_amount`
- `guarantee_counter_percentage`
- `guarantee_counter_amount`
- `confidi_guarantee_percentage`
- `confidi_guarantee_amount`
- `guarantee_regime`
- `guarantee_resolution_date`

## 5. Loan Information

- `loan_type`
- `loan_purpose`
- `loan_amount`
- `loan_duration_months`
- `loan_pre_amortization_months`
- `loan_amortization_type`
- `loan_interest_rate`
- `loan_taeg`
- `loan_contract_date`
- `loan_disbursement_date`
- `loan_maturity_date`
- `loan_resolution_bank_date`
- `loan_status`

## 6. Financial Situation and Installments

- `spread_rate`
- `reference_rate`
- `rendistato_rate`
- `nominal_rate`
- `effective_rate`
- `installment_amount`
- `installment_frequency`
- `installment_number`
- `residual_debt`

## 7. Availability of Core Documents

- `doc_application_present`
- `doc_admission_letter_present`
- `doc_financing_contract_present`
- `doc_disbursement_act_present`
- `doc_bank_resolution_present`
- `doc_annex_present`

## 8. Risk Event dan Recovery

- `risk_event_type`
- `risk_event_date`
- `first_default_date`
- `previous_risk_event_flag`
- `previous_risk_event_date`
- `exposure_detection_date`
- `risk_event_notice_date_to_mcc`
- `recovery_procedure_type`
- `recovery_start_act_date`
- `recovery_start_act_sent_date`
- `recovery_procedure_status`
- `recovery_amount_claimed`
- `recovery_amount_recovered`
- `recovery_amount_residual`

## 9. Claim dan Exposure

- `claim_type`
- `claim_submission_date`
- `claim_amount`
- `claim_guarantee_amount`
- `claim_residual_amount`
- `claim_protocol_number`
- `claim_channel`
- `claim_status`
- `exposure_total_amount`
- `exposure_principal_amount`
- `exposure_interest_amount`
- `exposure_penalty_amount`
- `exposure_measurement_date`

## 10. Legal Declaration and Evidence

- `decl_no_concordato`
- `decl_no_difficolta`
- `decl_no_inadempienze`
- `decl_no_pregiudizievoli`
- `decl_no_bankruptcy`
- `decl_no_liquidation`
- `decl_no_protest`
- `decl_no_default`
- `doc_decl_no_concordato_present`
- `doc_decl_no_difficolta_present`
- `doc_decl_no_inadempienze_present`
- `doc_decl_no_pregiudizievoli_present`

## 11. Credit Risk, Credit Bureau, dan Economic Documents

- `doc_rating_present`
- `doc_credit_risk_declaration_present`
- `doc_centrale_rischi_present`
- `doc_visura_present`
- `doc_ateco_present`
- `doc_financial_statement_present`
- `doc_credit_bureau_present`
- `cr_system_flag`
- `cr_system_last_update`
- `cr_default_flag`
- `cr_utp_flag`
- `cr_past_due_flag`
- `cr_bad_loans_flag`
- `credit_bureau_crif_flag`
- `credit_bureau_cerved_flag`

## 12. Commission, Variation, Suspension, dan Consolidation

- `commission_due_amount`
- `commission_paid_amount`
- `commission_integration_amount`
- `commission_payment_date`
- `commission_regime`
- `operation_variation_type`
- `operation_variation_date`
- `operation_variation_reason`
- `operation_variation_status`
- `suspension_requested_flag`
- `suspension_request_date`
- `suspension_start_date`
- `suspension_end_date`
- `suspension_resolution_date`
- `suspension_reason`
- `renegotiation_flag`
- `consolidation_flag`
- `consolidation_purpose`
- `consolidated_amount`
- `residual_debt_before_consolidation`

Important notes:

- Not all of the fields listed above are checked in v1.
- Not all of the fields listed above are directly used by v3 rules.
- Some v3 rules still use legacy field names such as `date_application`, `date_admission`, `amount_claimed`, `amount_guarantee`, `date_delibera`, and `date_bank_resolution`, which are normalized via aliases in the plugin.
