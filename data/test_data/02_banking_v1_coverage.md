# Banking Coverage Requirements for V1

In the banking plugin, v1 coverage refers to testing the completeness of inputs before proceeding to the more semantic policy evaluation. In the current implementation, v1 coverage is performed by `evaluate_v1_inputs()` in `plugins/banking/domain_plugin.py`. The logic checks three layers simultaneously: modern required fields from `REQUIRED_V1_FIELDS`, legacy required facts from `V1_REQUIRED_FACTS`, and required documents from `V1_REQUIRED_DOCS`.

In practical terms, the banking sector is considered sufficiently complete for v1 if the following minimum information is available.

## 1. Core business fields that must be filled in under “Observed”

These fields must contain values in `observed`:

- `operation_id`
- `fund_code`
- `fund_section`
- `guarantee_type`
- `guarantee_subtype`
- `process_type`
- `aid_regime`
- `lender_name`
- `beneficiary_name`
- `beneficiary_vat`
- `beneficiary_tax_code`
- `guarantee_issue_date`
- `guarantee_percentage`
- `guarantee_amount`
- `loan_amount`
- `loan_contract_date`
- `loan_disbursement_date`
- `risk_event_type`
- `risk_event_date`
- `first_default_date`
- `exposure_detection_date`
- `risk_event_notice_date_to_mcc`
- `recovery_start_act_date`
- `recovery_start_act_sent_date`
- `claim_type`
- `claim_submission_date`
- `claim_amount`
- `claim_guarantee_amount`
- `exposure_total_amount`
- `exposure_measurement_date`
- `decl_no_concordato`
- `decl_no_difficolta`
- `decl_no_inadempienze`
- `decl_no_pregiudizievoli`

If a field is empty, `None`, or an empty string, the plugin will generate code like `COV_REQUIRED_FACT_MISSING:<field_name>`.

## 2. Minimum required documents

The following field must be set to `true`:

- `doc_application_present`
- `doc_admission_letter_present`
- `doc_financing_contract_present`
- `doc_disbursement_act_present`

If either is not `true`, the plugin will generate 
 `COV_REQUIRED_DOC_MISSING:<field_name>`.

## 3. Legacy features that remain mandatory for v1 coverage

Although the field banking version has been updated, v1 still requires the following legacy features:

- `date_application`
- `date_admission`
- `date_contract`
- `date_disbursement`
- `amount_claimed`
- `amount_guarantee`
- `decl_no_concordato`

This is important because v1 coverage not only reads modern fields like `loan_contract_date` or `claim_amount`, but also checks the canonical legacy fields resulting from alias normalization. Therefore, to ensure v1 passes safely, the input should ensure that these aliases can be mapped.

## 4. Legacy documents that are also required for v1 coverage

In addition to modern field availability, v1 also enforces the presence of documents based on the following map:

- `DOC_KIND_APPLICATION` -> `doc_application_present`
- `DOC_KIND_ADMISSION` -> `doc_admission_letter_present`
- `DOC_KIND_CONTRACT` -> `doc_financing_contract_present`
- `DOC_KIND_DISBURSEMENT` -> `doc_disbursement_act_present`
- `DOC_KIND_DECL_NO_CONCORDATO` -> `doc_decl_no_concordato_present`

This means that to qualify for full v1 coverage, not only must the application, admission, contract, and disbursement documents be available, but also proof of a “no concordato” declaration.

## 5. A rule of thumb for qualifying for coverage v1

In practice, banking input is considered safe for v1 if it meets the following conditions:

- all factual fields in the v1 mandatory list are filled in;
- all minimum document availability fields have a value of `true`;
- legacy aliases such as `date_application`, `date_admission`, `date_contract`, `date_disbursement`, `amount_claimed`, and `amount_guarantee` are available directly or can be derived from modern fields;
- `doc_decl_no_concordato_present` is also set to `true`.

Implementation nuances:

- `date_admission` can be fulfilled from the alias `guarantee_issue_date`;
- `date_contract` can be fulfilled from the alias `loan_contract_date`;
- `date_disbursement` can be fulfilled from the alias `loan_disbursement_date`;
- `amount_claimed` can be populated from the alias `claim_amount`;
- `amount_guarantee` can be populated from the alias `claim_guarantee_amount` or `guarantee_amount`;
- `decl_no_concordato` has no other aliases, so this value must be explicitly provided.