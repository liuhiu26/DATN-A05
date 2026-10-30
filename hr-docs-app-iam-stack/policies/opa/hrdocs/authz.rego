# HR Docs: chính sách phân quyền RBAC (admin / manager / employee) + 6 quy tắc ABAC.
#
# FastAPI gọi  POST /v1/data/hrdocs/authz/decision  với input:
#   {
#     "action":   "document:read" | "document:update" | ... (xem bảng `decision` bên dưới),
#     "subject":  {"id": <Keycloak sub>, "role": "admin|manager|employee", "department": "IT"},
#     "resource": {"id", "owner_id", "department", "classification", "manager_id"},
#     "fields":   ["fullName", ...]            # chỉ dùng cho employee:update
#     "env":      {"ip": "10.0.0.5", "now_ns": 1760000000000000000}
#   }
# và nhận lại {"allow": bool, "rule": "<mã quy tắc>"}; `rule` được ghi vào trường policy_rule của log.
#
#   R1_OWNER               User chỉ đọc/sửa tài liệu có owner_id trùng user_id của mình
#   R2_DEPT_MANAGER        Manager đọc tài liệu có department trùng department của mình
#   R3_CONFIDENTIAL_HOURS  Tài liệu "confidential" chỉ đọc được trong giờ làm việc
#   R4_NO_SELF_ROLE_SALARY Không ai tự sửa role/salary của chính mình
#   R5_INTERNAL_IP         Xóa và thao tác quản trị chỉ từ dải IP nội bộ
#   R6_DEPT_REPORT         Manager không xem báo cáo của phòng ban khác
#   RBAC_ADMIN, EMP_SELF, EMP_DEPT_MANAGER, EMP_FIELD_ALLOWLIST, AUTHENTICATED, NO_ROLE, DEFAULT_DENY
#
# Tham số môi trường (giờ làm việc, múi giờ, dải IP nội bộ) nằm ở data.hrdocs.config,
# do config-init sinh từ .env (xem config-init/render.py).
package hrdocs.authz

cfg := data.hrdocs.config

roles := {"admin", "manager", "employee"}

self_editable := {"fullName", "phone", "address"}

admin_editable := {"fullName", "phone", "address", "position", "role", "salary", "department", "isActive"}

self_protected := {"role", "salary"}

allow(rule) := {"allow": true, "rule": rule}

deny(rule) := {"allow": false, "rule": rule}

# ---------------------------------------------------------------- thuộc tính

present(x) if {
	is_string(x)
	x != ""
}

has_role if input.subject.role in roles

is_admin if input.subject.role == "admin"

is_manager if input.subject.role == "manager"

is_owner if {
	present(input.subject.id)
	input.subject.id == input.resource.owner_id
}

is_self if {
	present(input.subject.id)
	input.subject.id == input.resource.id
}

same_department if {
	present(input.subject.department)
	input.subject.department == input.resource.department
}

dept_manager if {
	is_manager
	same_department
}

# R3: giờ làm việc [start, end) theo múi giờ cấu hình.
to_minutes(hhmm) := m if {
	parts := split(hhmm, ":")
	m := (to_number(parts[0]) * 60) + to_number(parts[1])
}

now_minutes := m if {
	[h, mi, _] := time.clock([input.env.now_ns, cfg.timezone])
	m := (h * 60) + mi
}

working_hours if {
	now_minutes >= to_minutes(cfg.work_hours.start)
	now_minutes < to_minutes(cfg.work_hours.end)
}

# R5: IP nguồn (do Kong chuyển tiếp) nằm trong dải nội bộ.
internal_ip if {
	some cidr in cfg.internal_cidrs
	net.cidr_contains(cidr, input.env.ip)
}

touches_protected if {
	some f in input.fields
	f in self_protected
}

fields_within(allowed) if {
	every f in input.fields {
		f in allowed
	}
}

# ---------------------------------------------------------------- quyết định

default decision := {"allow": false, "rule": "DEFAULT_DENY"}

decision := deny("NO_ROLE") if not has_role

decision := authenticated if {
	has_role
	input.action in {"profile:read", "document:list", "document:create", "employee:list", "department:list"}
}

decision := document_read if {
	has_role
	input.action == "document:read"
}

decision := document_update if {
	has_role
	input.action == "document:update"
}

decision := document_delete if {
	has_role
	input.action == "document:delete"
}

decision := employee_read if {
	has_role
	input.action == "employee:read"
}

decision := employee_update if {
	has_role
	input.action == "employee:update"
}

decision := department_report if {
	has_role
	input.action == "department:report"
}

decision := admin_access if {
	has_role
	input.action == "admin:access"
}

authenticated := allow("AUTHENTICATED")

# GET /documents/{id}: chủ sở hữu (R1), manager cùng phòng (R2), admin; confidential ngoài giờ bị chặn với mọi người (R3).
document_read := deny("R3_CONFIDENTIAL_HOURS") if {
	input.resource.classification == "confidential"
	not working_hours
} else := allow("RBAC_ADMIN") if {
	is_admin
} else := allow("R1_OWNER") if {
	is_owner
} else := allow("R2_DEPT_MANAGER") if {
	dept_manager
} else := deny("DEFAULT_DENY")

# PUT /documents/{id}: chủ sở hữu (R1), admin.
document_update := allow("RBAC_ADMIN") if {
	is_admin
} else := allow("R1_OWNER") if {
	is_owner
} else := deny("R1_OWNER")

# DELETE /documents/{id}: chỉ admin, và chỉ từ IP nội bộ (R5).
document_delete := deny("RBAC_ADMIN") if {
	not is_admin
} else := deny("R5_INTERNAL_IP") if {
	not internal_ip
} else := allow("RBAC_ADMIN")

# GET /employees/{id}: bản thân, manager cùng phòng, admin.
employee_read := allow("RBAC_ADMIN") if {
	is_admin
} else := allow("EMP_SELF") if {
	is_self
} else := allow("EMP_DEPT_MANAGER") if {
	dept_manager
} else := deny("DEFAULT_DENY")

# PATCH /employees/{id}: bản thân (fullName, phone, address), admin; không ai tự sửa role/salary (R4).
employee_update := deny("R4_NO_SELF_ROLE_SALARY") if {
	is_self
	touches_protected
} else := allow("RBAC_ADMIN") if {
	is_admin
	fields_within(admin_editable)
} else := deny("EMP_FIELD_ALLOWLIST") if {
	is_admin
} else := allow("EMP_SELF") if {
	is_self
	fields_within(self_editable)
} else := deny("EMP_FIELD_ALLOWLIST") if {
	is_self
} else := deny("DEFAULT_DENY")

# GET /departments/{id}/reports: admin, manager của chính phòng ban đó (R6).
department_report := allow("RBAC_ADMIN") if {
	is_admin
} else := allow("R6_DEPT_REPORT") if {
	dept_manager
	input.resource.manager_id == input.subject.id
} else := deny("R6_DEPT_REPORT") if {
	is_manager
} else := deny("DEFAULT_DENY")

# Mọi endpoint /admin/*: chỉ admin, và chỉ từ IP nội bộ (R5).
admin_access := deny("RBAC_ADMIN") if {
	not is_admin
} else := deny("R5_INTERNAL_IP") if {
	not internal_ip
} else := allow("RBAC_ADMIN")
