# tflint configuration — applies to all subdirectories when run with --recursive
# from the infra/ directory.

plugin "aws" {
  enabled = true
  version = "0.35.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

config {
  format           = "compact"
  call_module_type = "local"
}

# ── Naming conventions ────────────────────────────────────────────────────────
rule "terraform_naming_convention" {
  enabled = true

  variable {
    format = "snake_case"
  }

  locals {
    format = "snake_case"
  }

  output {
    format = "snake_case"
  }

  resource {
    format = "snake_case"
  }

  data {
    format = "snake_case"
  }
}

# ── Required metadata ─────────────────────────────────────────────────────────
rule "terraform_required_version" {
  enabled = true
}

rule "terraform_required_providers" {
  enabled = true
}

# ── Documentation ─────────────────────────────────────────────────────────────
rule "terraform_documented_variables" {
  enabled = true
}

rule "terraform_documented_outputs" {
  enabled = true
}

# ── Correctness ───────────────────────────────────────────────────────────────
rule "terraform_unused_declarations" {
  enabled = true
}

rule "terraform_deprecated_index" {
  enabled = true
}

rule "terraform_comment_syntax" {
  enabled = true
}
