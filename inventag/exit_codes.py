"""Exit codes of the ``inventag`` command. The one list; every module uses it.

====  =========================================================================
Code  Meaning
====  =========================================================================
0     Success (also when an account failed or nothing was found, unless one
      of the opt-in flags below is given).
1     Error: the run failed, a report format could not be written, or a
      configuration file or template is not valid.
2     Invalid or conflicting options, or ``--compliance-standard`` (not
      implemented).
3     Tag policy violations, when the config template sets
      ``fail_on_tag_violations``.
4     A security group rule at or above ``--risk-threshold``.
5     An account could not be scanned or ran out of time, with
      ``--fail-on-account-error``.
6     No resources to report, with ``--fail-if-empty``.
7     A policy finding failed at or above the threshold (``--policy-fail-on``
      on a scan, ``--fail-on`` of ``inventag policy check``).
8     A policy check could not be evaluated, with
      ``inventag policy check --fail-on-not-evaluated``.
====  =========================================================================

5 and 6 take precedence over 3 and 4, because the data behind 3 and 4 is
incomplete. Reports are written in all cases from 3 to 8. On a scan, 8 and 7
come only when none of 5, 6, 3 and 4 applies.
"""

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_TAG_VIOLATIONS = 3
EXIT_RISK_THRESHOLD = 4
EXIT_ACCOUNT_FAILED = 5
EXIT_NO_RESOURCES = 6
EXIT_POLICY_FAIL = 7
EXIT_POLICY_NOT_EVALUATED = 8
