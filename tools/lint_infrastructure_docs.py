from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INFRA_DIR = ROOT / "docs" / "infrastructure"
AWS_WAF_DIR = INFRA_DIR / "aws-waf-cloudfront"

REQUIRED_FILES = (
    INFRA_DIR / "README.md",
    AWS_WAF_DIR / "README.md",
    AWS_WAF_DIR / "main.tf",
    AWS_WAF_DIR / "variables.tf",
    AWS_WAF_DIR / "outputs.tf",
)

REQUIRED_SNIPPETS = {
    AWS_WAF_DIR / "main.tf": (
        'scope       = "CLOUDFRONT"',
        "AWSManagedRulesAmazonIpReputationList",
        "AWSManagedRulesAnonymousIpList",
        "AWSManagedRulesCommonRuleSet",
        "AWSManagedRulesKnownBadInputsRuleSet",
        "rate_based_statement",
        'aggregate_key_type = "IP"',
        'sampled_requests_enabled   = false',
    ),
    AWS_WAF_DIR / "variables.tf": (
        'variable "api_rate_limit_per_5_min"',
        'variable "enable_count_mode"',
    ),
    AWS_WAF_DIR / "outputs.tf": (
        'output "web_acl_arn"',
    ),
    INFRA_DIR / "README.md": (
        "票本文",
        "WAF/CDN",
    ),
}


def lint_infrastructure_docs(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for path in REQUIRED_FILES:
        target = root / path.relative_to(ROOT)
        if not target.is_file():
            issues.append(f"missing required infrastructure file: {_display_path(target, root)}")

    for path, snippets in REQUIRED_SNIPPETS.items():
        target = root / path.relative_to(ROOT)
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        for snippet in snippets:
            if snippet not in text:
                issues.append(f"{_display_path(target, root)} missing required snippet: {snippet}")

    main_tf = root / AWS_WAF_DIR.relative_to(ROOT) / "main.tf"
    if main_tf.is_file():
        sampled_request_lines = [
            line.strip()
            for line in main_tf.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("sampled_requests_enabled")
        ]
        if len(sampled_request_lines) < 5:
            issues.append("WAF sample must define sampled_requests_enabled on every rule")
        for line in sampled_request_lines:
            if line != "sampled_requests_enabled   = false":
                issues.append("WAF sample must keep sampled_requests_enabled   = false")

    return issues


def _display_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def main() -> None:
    issues = lint_infrastructure_docs()
    if issues:
        for issue in issues:
            print(f"Infrastructure docs lint error: {issue}", file=sys.stderr)
        raise SystemExit(1)
    print("Infrastructure docs lint passed")


if __name__ == "__main__":
    main()
