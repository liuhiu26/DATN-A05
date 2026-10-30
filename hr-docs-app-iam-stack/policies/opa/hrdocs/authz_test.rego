# Unit test cho chính sách. Chạy:  opa test policies/opa -v
# (hoặc: docker run --rm -v ./policies/opa:/p openpolicyagent/opa:1.21.2 test /p -v)
package hrdocs.authz_test

import data.hrdocs.authz

cfg := {
	"internal_cidrs": ["127.0.0.1/32", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
	"work_hours": {"start": "08:00", "end": "18:00"},
	"timezone": "Asia/Ho_Chi_Minh",
}

# 10:00 và 20:00 giờ Việt Nam (UTC+7)
in_hours := time.parse_rfc3339_ns("2026-10-15T03:00:00Z")

after_hours := time.parse_rfc3339_ns("2026-10-15T13:00:00Z")

admin := {"id": "u-admin", "role": "admin", "department": ""}

it_mgr := {"id": "u-itm", "role": "manager", "department": "IT"}

hr_mgr := {"id": "u-hrm", "role": "manager", "department": "HR"}

alice := {"id": "u-alice", "role": "employee", "department": "IT"}

bob := {"id": "u-bob", "role": "employee", "department": "IT"}

alice_doc := {"id": "d1", "owner_id": "u-alice", "department": "IT", "classification": "internal"}

alice_secret := {"id": "d2", "owner_id": "u-alice", "department": "IT", "classification": "confidential"}

it_dept := {"id": "IT", "department": "IT", "manager_id": "u-itm"}

hr_dept := {"id": "HR", "department": "HR", "manager_id": "u-hrm"}

decide(action, subject, resource, fields, ip, now) := d if {
	d := authz.decision with input as {
		"action": action,
		"subject": subject,
		"resource": resource,
		"fields": fields,
		"env": {"ip": ip, "now_ns": now},
	}
		with data.hrdocs.config as cfg
}

# R1
test_r1_owner_reads if decide("document:read", alice, alice_doc, [], "10.0.0.1", in_hours) == {"allow": true, "rule": "R1_OWNER"}

test_r1_other_employee_denied if decide("document:read", bob, alice_doc, [], "10.0.0.1", in_hours) == {"allow": false, "rule": "DEFAULT_DENY"}

test_r1_owner_updates if decide("document:update", alice, alice_doc, [], "10.0.0.1", in_hours).allow

test_r1_manager_cannot_update if decide("document:update", it_mgr, alice_doc, [], "10.0.0.1", in_hours) == {"allow": false, "rule": "R1_OWNER"}

# R2
test_r2_same_dept_manager_reads if decide("document:read", it_mgr, alice_doc, [], "10.0.0.1", in_hours) == {"allow": true, "rule": "R2_DEPT_MANAGER"}

test_r2_other_dept_manager_denied if not decide("document:read", hr_mgr, alice_doc, [], "10.0.0.1", in_hours).allow

# R3
test_r3_confidential_in_hours if decide("document:read", alice, alice_secret, [], "10.0.0.1", in_hours).allow

test_r3_confidential_after_hours if decide("document:read", alice, alice_secret, [], "10.0.0.1", after_hours) == {"allow": false, "rule": "R3_CONFIDENTIAL_HOURS"}

test_r3_applies_to_admin if decide("document:read", admin, alice_secret, [], "10.0.0.1", after_hours).rule == "R3_CONFIDENTIAL_HOURS"

test_r3_internal_doc_after_hours if decide("document:read", alice, alice_doc, [], "10.0.0.1", after_hours).allow

# R4
test_r4_self_salary_denied if decide("employee:update", alice, {"id": "u-alice", "department": "IT"}, ["salary"], "10.0.0.1", in_hours) == {"allow": false, "rule": "R4_NO_SELF_ROLE_SALARY"}

test_r4_admin_self_role_denied if decide("employee:update", admin, {"id": "u-admin"}, ["role"], "10.0.0.1", in_hours).rule == "R4_NO_SELF_ROLE_SALARY"

test_r4_admin_other_salary_allowed if decide("employee:update", admin, {"id": "u-alice"}, ["salary", "role"], "10.0.0.1", in_hours).allow

test_self_phone_allowed if decide("employee:update", alice, {"id": "u-alice"}, ["phone"], "10.0.0.1", in_hours) == {"allow": true, "rule": "EMP_SELF"}

test_self_position_denied if decide("employee:update", alice, {"id": "u-alice"}, ["position"], "10.0.0.1", in_hours).rule == "EMP_FIELD_ALLOWLIST"

test_manager_cannot_update_report if not decide("employee:update", it_mgr, {"id": "u-alice", "department": "IT"}, ["phone"], "10.0.0.1", in_hours).allow

# R5
test_r5_delete_internal if decide("document:delete", admin, alice_doc, [], "192.168.1.10", in_hours) == {"allow": true, "rule": "RBAC_ADMIN"}

test_r5_delete_external if decide("document:delete", admin, alice_doc, [], "203.0.113.7", in_hours) == {"allow": false, "rule": "R5_INTERNAL_IP"}

test_r5_admin_external if decide("admin:access", admin, {}, [], "203.0.113.7", in_hours).rule == "R5_INTERNAL_IP"

test_r5_owner_cannot_delete if decide("document:delete", alice, alice_doc, [], "10.0.0.1", in_hours) == {"allow": false, "rule": "RBAC_ADMIN"}

test_admin_access_manager_denied if decide("admin:access", it_mgr, {}, [], "10.0.0.1", in_hours).rule == "RBAC_ADMIN"

# R6
test_r6_own_dept_report if decide("department:report", it_mgr, it_dept, [], "10.0.0.1", in_hours) == {"allow": true, "rule": "R6_DEPT_REPORT"}

test_r6_other_dept_report if decide("department:report", it_mgr, hr_dept, [], "10.0.0.1", in_hours) == {"allow": false, "rule": "R6_DEPT_REPORT"}

test_r6_employee_report if decide("department:report", alice, it_dept, [], "10.0.0.1", in_hours).rule == "DEFAULT_DENY"

# Không có realm role của ứng dụng
test_no_role if decide("document:list", {"id": "x", "role": "", "department": ""}, {}, [], "10.0.0.1", in_hours) == {"allow": false, "rule": "NO_ROLE"}

test_unknown_action if decide("document:purge", admin, {}, [], "10.0.0.1", in_hours).rule == "DEFAULT_DENY"
