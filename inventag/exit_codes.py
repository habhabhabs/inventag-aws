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
5     An account could not be scanned (or only partly), with
      ``--fail-on-account-error``.
6     No resources to report, with ``--fail-if-empty``.
====  =========================================================================

5 and 6 take precedence over 3 and 4, because the data behind 3 and 4 is
incomplete. Reports are written in all cases from 3 to 6.
"""

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_TAG_VIOLATIONS = 3
EXIT_RISK_THRESHOLD = 4
EXIT_ACCOUNT_FAILED = 5
EXIT_NO_RESOURCES = 6
