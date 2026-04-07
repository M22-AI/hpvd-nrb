# Banking Rules for V3

In Banking v3, evaluation no longer focuses on coverage, but on policy outcomes. The final outcome is determined by a combination of gates and rules. In general:

- A final outcome of `PERMIT` means that no `FAIL` rules and no `WARN` rules have failed;
- a final result of `REVIEW` means there are no `FAIL`s, but at least one `WARN` has failed;
- a final result of `BLOCK` means at least one `FAIL` rule has failed;
- the result `NOT_EVALUATED` appears when the initial gate is not met, so v3 rules are not executed.

## 1. Initial Gate v3

Before the rules are executed, the banking plugin checks the following gate:

- `GATE-EP-1`: the `ep_status` field must be equal to `EP_KNOWN`

If `ep_status` is not equal to `EP_KNOWN`, the outcome immediately becomes `NOT_EVALUATED`. Therefore, the first requirement for v3 to be evaluated is to ensure that `ep_status = EP_KNOWN`.

## 2. Rules v3 that affect the outcome

### Rule V3-001

- Rule: `date_admission >= date_application`
- Severity: `FAIL`
- Failure reason code: `R_DATE_ADMISSION_BEFORE_APPLICATION`
- Related fields: `date_admission`, `date_application`

Business meaning: The admission date or the date the guarantee was issued must not be earlier than the application date. If it is earlier, the result is `BLOCK`.

### Rule V3-003

- Rule: `date_disbursement >= date_contract`
- Severity: `FAIL`
- Reason code on failure: `R_DISBURSEMENT_BEFORE_CONTRACT`
- Related fields: `date_disbursement`, `date_contract`

Business meaning: The disbursement date must not precede the contract date. If this rule is violated, the result is `BLOCK`.

### Rule V3-013

- Rule: `amount_claimed <= amount_guarantee`
- Severity: `FAIL`
- Failure reason code: `R_CLAIMED_GT_GUARANTEE`
- Related fields: `amount_claimed`, `amount_guarantee`

Business meaning: The claim amount must not exceed the guarantee amount specified by the rule. If `amount_claimed` is greater, the result is `BLOCK`.

### Rule V3-016

- Rule: `decl_no_concordato in [DV_TRUE, True]`
- Severity: `FAIL`
- Reason code on failure: `R_CONCORDATO_NOT_OK`
- Related field: `decl_no_concordato`

Business meaning: The no concordato declaration must be declared safe. The current implementation accepts two valid values:

- decision string `DV_TRUE`
- boolean `True`

If the value is `False`, `DV_FALSE`, empty, or any other value outside of these two forms, the result is `BLOCK`.

### Rule V3-024

- Rule: `date_delibera same_day date_bank_resolution`
- Severity: `WARN`
- Reason code on failure: `W_DATE_MISMATCH_DELIBERA`
- Related fields: `date_delibera`, `date_bank_resolution`

Business meaning: The deliberation date and the bank resolution date are expected to be on the same day. If they differ, this rule does not immediately block the process, but sets the outcome to `REVIEW` as long as there are no other `FAIL` conditions.

## 3. Conditions for Banking v3 to qualify as a PERMIT

For a banking input to pass v3 with the outcome `PERMIT`, the following minimum conditions must be met:

- `ep_status` must be `EP_KNOWN` for the evaluation to proceed;
- `date_admission` must be greater than or equal to `date_application`;
- `date_disbursement` must be greater than or equal to `date_contract`;
- `amount_claimed <= amount_guarantee`;
- `decl_no_concordato` must be `DV_TRUE` or `True`;
- `date_delibera` and `date_bank_resolution` must be the same date.

## 4. Conditions that result in a REVIEW

A banking input will be marked as `REVIEW` if:

- the gate passes;
- all `FAIL` rules pass;
- but rule `V3-024` fails, meaning `date_delibera` does not match the day of `date_bank_resolution`.

## 5. Conditions That Cause a BLOCK

A banking input will result in a `BLOCK` if the gate passes but any of the following `FAIL` rules fail:

- `date_admission < date_application`;
- `date_disbursement < date_contract`;
- `amount_claimed > amount_guarantee`;
- `decl_no_concordato` is neither `DV_TRUE` nor `True`.

## 6. Modern fields vs. legacy fields in v3

Although the banking inventory already contains many modern fields, v3 rules are currently still evaluated against the following legacy canonical fields:

- `date_application`
- `date_admission`
- `date_contract`
- `date_disbursement`
- `amount_claimed`
- `amount_guarantee`
- `date_delibera`
- `date_bank_resolution`
- `decl_no_concordato`

Therefore, for v3 to pass consistently, inputs must ensure that these legacy fields are present directly or can be normalized via plugin aliases. The available alias mappings are:

- `date_admission` <- `guarantee_issue_date`
- `date_contract` <- `loan_contract_date`
- `date_disbursement` <- `loan_disbursement_date`
- `amount_claimed` <- `claim_amount`
- `amount_guarantee` <- `claim_guarantee_amount` or `guarantee_amount`
- `date_bank_resolution` <- `loan_resolution_bank_date`
- `date_delibera` <- `guarantee_resolution_date`

There are no additional aliases for `decl_no_concordato`, so this field must be present and set to true.
